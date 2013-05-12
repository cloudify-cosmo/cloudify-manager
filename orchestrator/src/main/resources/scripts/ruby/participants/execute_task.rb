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

java_import java::net::URI
java_import org.cloudifysource::cosmo::tasks::messages::ExecuteTaskMessage
java_import org.cloudifysource::cosmo::tasks::messages::TaskStatusMessage
java_import org.cloudifysource::cosmo::tasks::messages::TaskMessage
java_import java::util::UUID
java_import com::google::common::util::concurrent::FutureCallback
java_import com::google::common::util::concurrent::Futures
java_import java::lang::RuntimeException
java_import org.cloudifysource::cosmo::messaging::consumer::MessageConsumerListener


class ExecuteTaskParticipant < Ruote::Participant
  include FutureCallback
  include MessageConsumerListener

  @message_consumer   # used for listening to task status reply messages
  @new_task           # the new executed task message
  @target_uri         # the target executor's URI (topic) the task is addressed to

  def do_not_thread
    true
  end

  def on_workitem
    begin
      raise 'message_producer not set' unless $ruote_properties.has_key? 'message_producer'
      raise 'message_consumer not set' unless $ruote_properties.has_key? 'message_consumer'
      raise 'target parameter not set' unless workitem.params.has_key? 'target'

      @message_consumer.remove_listener(self)

      if workitem.params.has_key? 'continue_on'
        @continue_on = workitem.params['continue_on']
      else
        @continue_on = TaskStatusMessage.SENT
      end

      message_producer = $ruote_properties['message_producer']
      @message_consumer = $ruote_properties['message_consumer']
      target = workitem.params['target']
      sender = 'execute_task_participant'

      payload = nil
      if workitem.params.has_key?('payload')
        payload = to_map(workitem.params['payload'])
      end

      @new_task = create_task_message(target, sender, payload)
      $logger.debug('Executing task message: {}', @new_task)

      @target_uri = URI.new(target)

      future = message_producer.send(@target_uri, @new_task)
      Futures.add_callback(future, self)

    rescue Exception => e
      $logger.debug('Exception caught on execute_task participant execution: {}', e)
      raise e
    end
  end

  def create_task_message(target, sender, payload)
    task = ExecuteTaskMessage.new
    task.set_task_id(UUID.random_uuid.to_string)
    task.set_target(target)
    task.set_sender(sender)
    task.set_payload(payload)
    task
  end

  def onSuccess(result)
    $logger.debug('Message producer callback invoked [status={}]', result.get_status_code)
    if result.get_status_code != 200
      onFailure(RuntimeException.new("HTTP status code is: #{result.get_status_code}"))
    else
      if @continue_on.eql? TaskStatusMessage.SENT
        reply(workitem)
      else
        @message_consumer.add_listener(@target_uri, self)
      end
    end
  end

  def onMessage(uri, message)
    $logger.debug('Message consumer listener received message: {}', message)
    begin
      if message.java_kind_of? TaskStatusMessage and message.get_task_id.eql? @new_task.get_task_id
        $logger.debug('Received task status matches sent task! [continue_on={}]', @continue_on)
        if message.get_status.eql? @continue_on
          $logger.debug('Received task status: {}', message)
          @message_consumer.remove_listener(self)
          reply(workitem)
        end
      end
    rescue Exception => e
      onFailure(e)
    end
  end

  def onFailure(error)
    $logger.error('Exception on message producer callback: {}', error)
    @message_consumer.remove_listener(self)
  end

end
