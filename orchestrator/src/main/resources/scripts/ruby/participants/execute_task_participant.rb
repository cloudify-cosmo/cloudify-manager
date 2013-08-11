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
require 'prepare_operation_participant'

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
  EVENT_RESULT = 'result'
  RESULT_WORKITEM_FIELD = 'to_f'
  TASK_SUCCEEDED = 'task-succeeded'
  TASK_FAILED = 'task-failed'
  TASK_REVOKED = 'task-revoked'

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
        safe_merge!(payload_properties, payload_params)
      end
      if payload.has_key? RELATIONSHIP_PROPERTIES
        relationship_properties = payload[RELATIONSHIP_PROPERTIES]
        safe_merge!(payload_properties, relationship_properties)
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
      $logger.debug("Exception caught on execute_task participant: #{e}")
      flunk(workitem, e)
    end
  end

  def onTaskEvent(taskId, eventType, jsonEvent)
    begin
      event_data = JSON.parse(jsonEvent.to_s)
      event_data['wfid'] = workitem.wfid
      $logger.debug('[event] {}', JSON.generate(event_data))
      if eventType == TASK_SUCCEEDED
        if workitem.params.has_key? RESULT_WORKITEM_FIELD
          result_field = workitem.params[RESULT_WORKITEM_FIELD]
          workitem.fields[result_field] = event_data[EVENT_RESULT] unless result_field.empty?
        end
        reply(workitem)
      elsif eventType == TASK_FAILED || eventType == TASK_REVOKED
        flunk(workitem, Exception.new(event_data['exception']))
      end
    rescue => e
      backtrace = e.backtrace if e.respond_to?(:backtrace)
      $logger.debug("Exception handling task event #{jsonEvent}: #{e.to_s} / #{backtrace}. ")
      flunk(workitem, e)
    end
  end

  def safe_merge!(merge_into, merge_from)
    merge_from.each do |key, value|
      if merge_into.has_key? key
        raise "Target map already contains key: #{key}"
      end
      merge_into[key] = value
    end
    merge_into
  end

end
