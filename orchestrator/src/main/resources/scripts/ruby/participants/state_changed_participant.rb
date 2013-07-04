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

java_import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage
java_import java.net.URI
java_import com::google::common::util::concurrent::FutureCallback
java_import com::google::common::util::concurrent::Futures

class StateChangedParticipant < Ruote::Participant
  include FutureCallback

  def on_workitem
    begin
      resource_id = workitem.fields['resource_id']
      producer = $ruote_properties['message_producer']
      state_cache_topic = $ruote_properties['state_cache_topic']
      state = workitem.params['state']

      $logger.debug('Executing StateChangedParticipant [resourceId={}, state={}]', resource_id, state)

      raise 'resource_id is not set' unless defined? resource_id and not resource_id.nil?
      raise 'message_producer not set' unless defined? producer
      raise 'state_cache_topic not set' unless defined? state_cache_topic
      raise 'state not set' unless defined? state

      uri = URI.new(state_cache_topic)
      message = StateChangedMessage.new
      message.set_resource_id(resource_id)
      message.set_state(state)

      $logger.debug('Sending state changed message [uri={}, message={}]', uri, message)

      future = producer.send(uri, message)
      Futures.add_callback(future, self)
    end
  end

  def onSuccess(result)
    reply(workitem)
  end

  def onFailure(error)
    flunk(workitem, error)
  end

  def do_not_thread
    true
  end

end
