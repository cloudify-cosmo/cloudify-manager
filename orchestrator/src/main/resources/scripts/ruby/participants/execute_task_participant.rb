#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

java_import org.cloudifysource::cosmo::tasks::TaskEventListener
java_import org.cloudifysource::cosmo::tasks::TaskExecutor

require 'json'
require 'securerandom'
require 'set'

class ExecuteTaskParticipant < Ruote::Participant
  include TaskEventListener

  EXECUTOR = 'executor'
  TARGET = 'target'
  EXEC = 'exec'
  PROPERTIES = 'properties'
  RELATIONSHIP_PROPERTIES = 'relationship_properties'
  PARAMS = 'params'
  PAYLOAD = 'payload'
  NODE = 'node'
  NODE_ID = '__cloudify_id'
  CLOUDIFY_RUNTIME = 'cloudify_runtime'
  EVENT_RESULT = 'result'
  RESULT_WORKITEM_FIELD = 'to_f'
  TASK_SUCCEEDED = 'task-succeeded'
  TASK_FAILED = 'task-failed'
  TASK_REVOKED = 'task-revoked'

  RELOAD_RIEMANN_CONFIG_TASK_NAME = 'cosmo.cloudify.tosca.artifacts.plugin.riemann_config_loader.tasks.reload_riemann_config'
  VERIFY_PLUGIN_TASK_NAME = 'cosmo.cloudify.tosca.artifacts.plugin.plugin_installer.tasks.verify_plugin'
  RESTART_CELERY_WORKER_TASK_NAME = 'cosmo.cloudify.tosca.artifacts.plugin.worker_installer.tasks.restart'

  TASK_TO_FILTER = Set.new [RELOAD_RIEMANN_CONFIG_TASK_NAME, VERIFY_PLUGIN_TASK_NAME, RESTART_CELERY_WORKER_TASK_NAME]

  def colorize(color_code, message)
    "\e[#{color_code}m#{message}\e[0m"
  end

  def red(message)
    colorize(31, message)
  end

  def green(message)
    colorize(32, message)
  end

  def yellow(message)
    colorize(33, message)
  end


  def do_not_thread
    true
  end

  def on_workitem
    begin
      raise 'executor not set' unless $ruote_properties.has_key? EXECUTOR
      raise 'target parameter not set' unless workitem.params.has_key? TARGET
      raise 'exec not set' unless workitem.params.has_key? EXEC

      executor = $ruote_properties[EXECUTOR]

      exec = workitem.params[EXEC]
      target = workitem.params[TARGET]
      payload = to_map(workitem.params[PAYLOAD])

      $logger.debug('Received task execution request [target={}, exec={}, payload={}]', target, exec, payload)

      task_id = SecureRandom.uuid
      payload_properties = payload[PROPERTIES] || Hash.new
      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        payload_properties[NODE_ID] = node['id']
      end
      final_properties = Hash.new
      safe_merge!(final_properties, payload_properties)
      if payload.has_key? PARAMS
        payload_params = payload[PARAMS] || Hash.new
        safe_merge!(final_properties, payload_params)
      end
      if payload.has_key? RELATIONSHIP_PROPERTIES
        relationship_properties = payload[RELATIONSHIP_PROPERTIES] || Hash.new
        safe_merge!(final_properties, relationship_properties)
      end
      properties = to_map(final_properties)

      $logger.debug('Executing task [taskId={}, target={}, exec={}, properties={}]',
                    task_id,
                    target,
                    exec,
                    properties)

      json_props = JSON.generate(properties)

      $logger.debug('Generated JSON from {} = {}', properties, json_props)

      executor.send_task(target, task_id, exec, json_props, self)

    rescue Exception => e
      $logger.debug("Exception caught on execute_task participant: #{e}")
      flunk(workitem, e)
    end
  end

  def onTaskEvent(taskId, eventType, jsonEvent)
    begin

      enriched_event = JSON.parse(jsonEvent.to_s)
      enriched_event['wfid'] = workitem.wfid
      enriched_event['wfname'] = workitem.sub_wf_name

      # if we are in the context of a node
      # we should enrich the event even further.
      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        parts = node['id'].split('.')
        enriched_event['node_id'] = parts[1]
        enriched_event['app_id'] = parts[0]
      end

      # log every event coming from task executions.
      # this log will not be displayed to the user by default
      $logger.debug('[event] {}', JSON.generate(enriched_event))

      full_task_name = get(taskId)
      if full_task_name.nil?
        full_task_name = enriched_event['name']
      end
      unless full_task_name.nil?
        enriched_event['plugin'] = get_plugin_name_from_task(full_task_name)
        enriched_event['task_name'] = get_short_name_from_task_name(full_task_name)
      end

      description = event_to_s(enriched_event)

      case eventType

        when 'task-received'

          # worker received the task and is about to execute it
          # save the task name for future reference

          put(taskId, full_task_name)

        when 'task-started'

          unless TASK_TO_FILTER.include? full_task_name
            $user_logger.debug(description)
          end

        when 'task-succeeded'

          if workitem.params.has_key? RESULT_WORKITEM_FIELD
            result_field = workitem.params[RESULT_WORKITEM_FIELD]
            workitem.fields[result_field] = fix_task_result(enriched_event[EVENT_RESULT]) unless result_field.empty?
          end
          unless TASK_TO_FILTER.include? full_task_name
            $user_logger.debug(green(description))
          end
          reply(workitem)

        when 'task-failed' || 'task-revoked'

          unless full_task_name == VERIFY_PLUGIN_TASK_NAME
            $user_logger.debug(red(description))
          end
          flunk(workitem, Exception.new(enriched_event['exception']))
        else

      end
    rescue => e
      backtrace = e.backtrace if e.respond_to?(:backtrace)
      $logger.debug("Exception handling task event #{jsonEvent}: #{e.to_s} / #{backtrace}. ")
      flunk(workitem, e)
    end
  end

  # temporary workaround to fix literal results of python tasks
  def fix_task_result(raw_result)
    final_result = raw_result
    if raw_result.length >= 2 && raw_result[0] == "'" && raw_result[-1] == "'"
      final_result = raw_result[1...-1]
    end
    final_result
  end

  def safe_merge!(merge_into, merge_from)
    merge_from.each do |key, value|
      if key == CLOUDIFY_RUNTIME
        # TODO maybe also merge cloudify_runtime items with the same id
        merge_into[CLOUDIFY_RUNTIME] = Hash.new unless merge_into.has_key? CLOUDIFY_RUNTIME
        merge_into[CLOUDIFY_RUNTIME].merge!(value)
      elsif merge_into.has_key? key
        raise "Target map already contains key: #{key}"
      else
        merge_into[key] = value
      end
    end
    merge_into
  end

  def event_to_s(event)

    new_event = {'name' => event['task_name'], 'plugin' => event['plugin'], 'app' => event['app_id'],
                 'node' => event['node_id'], 'workflow_id' => event['wfid'], 'workflow_name' => event['wfname']}
    unless event['exception'].nil?
      new_event['error'] = event['exception']
      new_event['trace'] = event['traceback']
    end

    "[#{event['type']}] - #{new_event}"

  end

  def get_plugin_name_from_task(full_task_name)
    if full_task_name.include?('.tasks.')
      return full_task_name.split('.tasks.')[0].split('.')[-1]
    end
    full_task_name
  end

  def get_short_name_from_task_name(full_task_name)
    if full_task_name.include?('.tasks.')
      return full_task_name.split('.tasks.')[1]
    end
    full_task_name
  end

end
