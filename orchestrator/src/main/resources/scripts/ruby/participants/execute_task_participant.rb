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

  def do_not_thread
    true
  end

  def on_workitem
    begin
      raise 'executor not set' unless $ruote_properties.has_key? 'executor'
      raise 'target parameter not set' unless workitem.params.has_key? 'target'
      raise 'exec not set' unless workitem.params.has_key? 'exec'

      executor = $ruote_properties['executor']

      task_id = SecureRandom.uuid

      $logger.debug('task id is {}', task_id)

      exec = workitem.params['exec']

      $logger.debug('exec is {}', exec)

      target = workitem.params['target']

      $logger.debug('target is {}', target)

      payload = to_map(workitem.params['payload'])

      properties = to_map(payload['properties'])

      $logger.debug('Executing task {} with payload {}', exec, payload)

      json_props = JSON.generate(properties)

      $logger.debug('Generated JSON from {} = {}', properties, json_props)

      exec = "cosmo.#{target}.#{exec}"

      executor.sendTask(target, task_id, exec, json_props, self)

    rescue Exception => e
      $logger.debug('Exception caught on execute_task participant', e)
      flunk(workitem, e)
    end
  end

  def onTaskSucceeded(success_event)
    $logger.debug('Task Succeeded:' + success_event)
    reply(workitem)
  end

  def onTaskFailed(fail_event)
    $logger.debug('Task Failed:' + fail_event)
    flunk(workitem, Exception.new(JSON.parse(fail_event)['exception']))
  end

end
