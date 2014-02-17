#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
#

require 'json'
require 'securerandom'
require 'set'
require_relative 'prepare_operation_participant'
require_relative 'exception_logger'
require_relative '../amqp/amqp_client'
require_relative '../utils/logs'
require_relative '../utils/events'


class ExecuteTaskParticipant < Ruote::Participant

  @full_task_name = nil
  @task_arguments = nil

  EXECUTOR = 'executor'
  TARGET = 'target'
  EXEC = 'exec'
  PROPERTIES = 'properties'

  PARAMS = 'params'
  PAYLOAD = 'payload'
  ARGUMENT_NAMES = 'argument_names'
  NODE = 'node'
  PLAN = 'plan'
  NODE_ID = '__cloudify_id'
  CLOUDIFY_RUNTIME = 'cloudify_runtime'
  EVENT_RESULT = 'result'
  RESULT_WORKITEM_FIELD = 'to_f'
  SENDING_TASK = 'sending-task'
  TASK_SUCCEEDED = 'task-succeeded'
  TASK_STARTED = 'task-started'
  TASK_FAILED = 'task-failed'
  TASK_REVOKED = 'task-revoked'

  RELATIONSHIP_PROPERTIES = 'relationship_properties'
  RUOTE_RELATIONSHIP_NODE_ID = PrepareOperationParticipant::RUOTE_RELATIONSHIP_NODE_ID
  SOURCE_NODE_ID = '__source_cloudify_id'
  TARGET_NODE_ID = '__target_cloudify_id'
  RUN_NODE_ID = '__run_on_node_cloudify_id'
  SOURCE_NODE_PROPERTIES = '__source_properties'
  TARGET_NODE_PROPERTIES = '__target_properties'
  RELATIONSHIP_NODE = 'relationship_other_node'

  VERIFY_PLUGIN_TASK_NAME = 'plugin_installer.tasks.verify_plugin'
  GET_ARGUMENTS_TASK_NAME = 'plugin_installer.tasks.get_arguments'
  RESTART_CELERY_WORKER_TASK_NAME = 'worker_installer.tasks.restart'
  GET_KV_STORE_TASK_NAME = 'kv_store.tasks.get'
  PUT_KV_STORE_TASK_NAME = 'kv_store.tasks.put'

  TASK_TO_FILTER = Set.new [VERIFY_PLUGIN_TASK_NAME,
                            RESTART_CELERY_WORKER_TASK_NAME,
                            GET_ARGUMENTS_TASK_NAME,
                            GET_KV_STORE_TASK_NAME,
                            PUT_KV_STORE_TASK_NAME]

  def do_not_thread
    true
  end

  def on_workitem
    begin
      raise 'executor not set' unless $ruote_properties.has_key? EXECUTOR
      raise 'target parameter not set' unless workitem.params.has_key? TARGET
      raise 'exec not set' unless workitem.params.has_key? EXEC

      executor = $ruote_properties[EXECUTOR]

      @full_task_name = workitem.params[EXEC]
      @target = workitem.params[TARGET]
      @task_id = SecureRandom.uuid
      payload = to_map(workitem.params[PAYLOAD])
      argument_names = workitem.params[ARGUMENT_NAMES]

      log_task(:debug,
               "Received task execution request [target=#{@target}, name=#{@full_task_name}, payload=#{payload}, argument_names=#{argument_names}]", {
              :payload => payload,
              :argument_names => argument_names
          })

      if workitem.fields.has_key?(RUOTE_RELATIONSHIP_NODE_ID) && @full_task_name != VERIFY_PLUGIN_TASK_NAME && @full_task_name != GET_ARGUMENTS_TASK_NAME
        final_properties = Hash.new
      else
        final_properties = payload[PROPERTIES] || Hash.new
        final_properties[NODE_ID] = workitem.fields[NODE]['id'] if workitem.fields.has_key? NODE
      end

      safe_merge!(final_properties, payload[PARAMS] || Hash.new)
      add_cloudify_context_to_properties(final_properties, payload)

      properties = to_map(final_properties)

      @task_arguments = extract_task_arguments(properties, argument_names)

      log_task(:debug,
               "Executing task [taskId=#{@task_id}, target=#{@target}, name=#{@full_task_name}, properties=#{properties}]", {
              :properties => properties
          })

      unless TASK_TO_FILTER.include? @full_task_name
        send_task_event(:sending_task)
      end

      executor.send_task(@target, @task_id, @full_task_name, properties, self)

    rescue => e
      log_exception(workitem, e, 'execute_task')
      flunk(workitem, e)
    end
  end

  def send_task_event(event_type, custom_message=nil)
    case event_type
      when :sending_task
        message = "Sending task '#{@full_task_name}'"
      when :task_started
        message = "Task started '#{@full_task_name}'"
      when :task_failed
        message = "Task failed '#{@full_task_name}'"
      when :task_succeeded
        message = "Task succeeded '#{@full_task_name}'"
    end
    if not custom_message.nil?
      message = "#{message} -> #{custom_message}"
    end
    event(event_type, {
      :workitem => workitem,
      :message => message,
      :task_id => @task_id,
      :task_name => @full_task_name,
      :task_target => @target,
      :plugin => workitem.fields['plugin_name'] || nil,
      :operation => workitem.fields['node_operation'] || nil
    })
  end

  def log_task(level, message, arguments)
    log(level, message, {
      :workitem => workitem,
      :task_id => @task_id,
      :task_name => @full_task_name,
      :task_target => @target,
      :plugin => workitem.fields['plugin_name'] || nil,
      :operation => workitem.fields['node_operation'] || nil,
      :arguments => arguments
    })
  end

  def add_cloudify_context_to_properties(props, payload)
    context = Hash.new
    context['__cloudify_context'] = '0.3'
    context[:wfid] = workitem.wfid
    node_id = nil
    node_name = nil
    node_properties = nil

    if workitem.fields.has_key? RUOTE_RELATIONSHIP_NODE_ID
      source_id = workitem.fields[NODE]['id']
      target_id = workitem.fields[RELATIONSHIP_NODE]['id']
      source_properties = payload[PROPERTIES] || Hash.new
      target_properties = payload[RELATIONSHIP_PROPERTIES] || Hash.new
      relationship_node_id = workitem.fields[RUOTE_RELATIONSHIP_NODE_ID]

      if relationship_node_id == source_id
        node_id = target_id
        node_properties = target_properties.clone
        related_node_id = source_id
        related_node_properties = source_properties.clone
      else
        node_id = source_id
        node_properties = source_properties.clone
        related_node_id = target_id
        related_node_properties = target_properties.clone
      end

      unless workitem.fields.has_key? PlanHolder::EXECUTION_ID
        raise 'execution_id field not set'
      end
      execution_id = workitem.fields[PlanHolder::EXECUTION_ID]
      node_in_context = PlanHolder.get_node(execution_id, node_id)
      node_name = node_in_context['name']

      node_properties.delete(CLOUDIFY_RUNTIME)
      related_node_properties.delete(CLOUDIFY_RUNTIME)

      context[:related] = {
          :node_id => related_node_id,
          :node_properties => related_node_properties
      }
    elsif workitem.fields.has_key? NODE
      node_id = workitem.fields[NODE]['id'] || nil
      node_name = workitem.fields[NODE]['name'] || nil
      if payload.has_key? PROPERTIES
        node_properties = payload[PROPERTIES].clone
        node_properties.delete(NODE_ID)
        node_properties.delete(CLOUDIFY_RUNTIME)
      end
    end

    context[:node_id] = node_id
    context[:node_name] = node_name
    context[:node_properties] = node_properties
    context[:task_id] = @task_id
    context[:task_name] = @full_task_name
    context[:task_target] = @target
    context[:plugin] = workitem.fields[PrepareOperationParticipant::PLUGIN_NAME] || nil
    context[:operation] = workitem.fields[PrepareOperationParticipant::NODE_OPERATION] || nil
    context[:blueprint_id] = workitem.fields['blueprint_id'] || nil
    context[:deployment_id] = workitem.fields['deployment_id'] || nil
    context[:execution_id] = workitem.fields['execution_id'] || nil
    context[:workflow_id] = workitem.fields['workflow_id'] || nil
    if props.has_key? CLOUDIFY_RUNTIME
      context[:capabilities] = props[CLOUDIFY_RUNTIME]
    end
    props['__cloudify_context'] = context
  end


  def populate_event_content(event, task_id, log_debug)
    sub_workflow_name = workitem.sub_wf_name
    workflow_name = workitem.wf_name
    if sub_workflow_name == workflow_name
      # no need to print sub workflow if there is none
      event['wfname'] = workflow_name
    else
      event['wfname'] = "#{workflow_name}.#{sub_workflow_name}"
    end

    event['wfid'] = workitem.wfid

    # if we are in the context of a node
    # we should enrich the event even further.
    if workitem.fields.has_key? NODE
      node = workitem.fields[NODE]
      event['node_id'] = node['id']
    end
    plan = PlanHolder.get(workitem[PlanHolder::EXECUTION_ID])
    unless plan.nil?
      event['app_id'] = plan['name']
    end

    # log every event coming from task executions.
    # this log will not be displayed to the user by default
    if log_debug
      log_task(:debug, "task event: #{event}", {
          :event => event
      })
    end

    if @full_task_name.nil?
      raise "task_name for task with id #{task_id} is null"
    end
    event['plugin'] = get_plugin_name_from_task(@full_task_name)
    event['task_name'] = get_short_name_from_task_name(@full_task_name)

  end

  def extract_task_arguments(properties, argument_names)
    props = {}
    unless argument_names.nil?
      args = argument_names.gsub('[','').gsub(']','').gsub("'",'')
      args = args.split(',')
      for name in args
        name = name.gsub(' ','')
        props[name] = properties[name]
      end
    end
    props
  end

  def onTaskEvent(task_id, event_type, event)
    begin

      enriched_event = event

      populate_event_content(enriched_event, task_id, true)

      case event_type

        when TASK_STARTED
          unless TASK_TO_FILTER.include? @full_task_name
            send_task_event(:task_started)
          end

        when TASK_SUCCEEDED

          if workitem.params.has_key? RESULT_WORKITEM_FIELD
            result_field = workitem.params[RESULT_WORKITEM_FIELD]
            workitem.fields[result_field] = fix_task_result(enriched_event[EVENT_RESULT]) unless result_field.empty?
          end
          unless TASK_TO_FILTER.include? @full_task_name
            send_task_event(:task_succeeded)
          end
          reply(workitem)

        when TASK_FAILED || TASK_REVOKED

          unless @full_task_name == VERIFY_PLUGIN_TASK_NAME
            send_task_event(:task_failed, enriched_event['exception'])
          end
          flunk(workitem, Exception.new(enriched_event['exception']))

        else
          # ignore...
      end
    rescue => e
      log_exception(workitem, e, 'execute_task')
      flunk(workitem, e)
    end
  end

  # temporary workaround to fix literal results of python tasks
  def fix_task_result(raw_result)

      if raw_result.length >= 2 && raw_result[0] == "'" && raw_result[-1] == "'"
        final_result = raw_result[1...-1]
        final_result.gsub!("\\\\","\\")
        final_result.gsub!("\\'","'")
      else
        final_result = raw_result
      end

      begin
          final_result = JSON.parse(final_result)
      rescue => e
        # ignore, not valid JSON, probably a string
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

  def dict_to_s(dict)
    JSON.pretty_generate(dict)
  end

  def to_map(java_map)
    map = Hash.new
    unless java_map.nil?
      java_map.each { |key, value| map[key] = value }
    end
    map
  end

end
