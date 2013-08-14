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
  PARAMS = 'params'
  PAYLOAD = 'payload'
  NODE = 'node'
  NODE_ID = '__cloudify_id'

  RELOAD_RIEMANN_CONFIG_TASK_NAME = 'cosmo.cloudify.tosca.artifacts.plugin.riemann.config_loader.tasks.reload_riemann_config'
  VERIFY_PLUGIN_TASK_NAME = 'cosmo.cloudify.tosca.artifacts.plugin.plugin_installer.installer.tasks.verify_plugin'
  RESTART_CELERY_WORKER_TASK_NAME = 'cosmo.cloudify.tosca.artifacts.plugin.celery_worker.installer.tasks.restart'

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
      payload_properties = payload[PROPERTIES]
      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        payload_properties[NODE_ID] = node['id']
      end
      if payload.has_key? PARAMS
        payload_params = payload[PARAMS]
        payload_properties.merge! payload_params if payload_params.respond_to? 'merge'
      end
      properties = to_map(payload_properties)

      $logger.debug('Executing task [taskId={}, target={}, exec={}, properties={}]',
                    task_id,
                    target,
                    exec,
                    properties)

      json_props = JSON.generate(properties)

      $logger.debug('Generated JSON from {} = {}', properties, json_props)

      executor.send_task(target, task_id, exec, json_props, self)

    rescue Exception => e
      $logger.debug('Exception caught on execute_task participant ->', e)
      flunk(workitem, e)
    end
  end

  def onTaskEvent(taskId, eventType, jsonEvent)
    begin

      enriched_event = JSON.parse(jsonEvent.to_s)
      enriched_event['wfid'] = workitem.wfid
      enriched_event['wfname'] = workitem.wf_name

      # if we are in the context of a node
      # we should enrich the event even further.
      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        enriched_event['node_id'] = node['id'].split('.')[1]
        enriched_event['app_id'] = node['id'].split('.')[0]
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

          unless TASK_TO_FILTER.include? full_task_name
            $user_logger.debug(green(description))
          end
          reply(workitem)

        when 'task-failed' || 'task-revoked'

          unless TASK_TO_FILTER.include? full_task_name
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

  def event_to_s(event)

    new_event = {'name' => event['task_name'], 'plugin' => event['plugin'], 'app' => event['app_id'],
                 'node' => event['node_id'], 'worflow_id' => event['wfid'], 'workflow_name' => event['wfname']}
    unless event['exception'].nil?
      new_event['error'] = event['exception']
    end

    "[#{event['type']}] - #{new_event}"

  end

  def get_plugin_name_from_task(full_task_name)
    full_task_name.split('cosmo.cloudify.tosca.artifacts.plugin.')[1].split('.tasks.')[0]
  end

  def get_short_name_from_task_name(full_task_name)
    full_task_name.split('.tasks.')[1]
  end

end
