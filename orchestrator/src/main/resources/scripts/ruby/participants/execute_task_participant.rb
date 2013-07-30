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

java_import org.cloudifysource::cosmo::tasks::EventListener
java_import org.cloudifysource::cosmo::tasks::TaskExecutor

require 'json'
require 'securerandom'


class ExecuteTaskParticipant < Ruote::Participant
  include EventListener

  EXECUTOR = 'executor'
  TARGET = 'target'
  EXEC = 'exec'
  PROPERTIES = 'properties'
  PARAMS = 'params'
  PAYLOAD = 'payload'
  NODE = 'node'
  NODE_ID = '__cloudify_id'

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

  def onTaskSucceeded(success_event)
    log_event(success_event)
    reply(workitem)
  end

  def onTaskFailed(fail_event)
    log_event(fail_event)
    flunk(workitem, Exception.new(JSON.parse(fail_event)['exception']))
  end

  def log_event(event)
    begin
      enriched_event = JSON.parse(event.to_s)
      enriched_event['wfid'] = workitem.wfid
      $logger.debug('[event] ' +JSON.generate(enriched_event))
    rescue => e
      backtrace = e.backtrace if e.respond_to?(:backtrace)
      $logger.debug("error logging event: #{e.to_s} / #{backtrace}")
    end
  end

end
