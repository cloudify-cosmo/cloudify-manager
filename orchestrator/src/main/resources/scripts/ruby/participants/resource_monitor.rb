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

java_import org.cloudifysource.cosmo.cep.messages.ResourceMonitorMessage

class ResourceMonitorParticipant < Ruote::Participant
  def on_workitem
    begin
      resource_id = workitem.fields['resource_id']
      producer = $ruote_properties['message_producer']
      broker_uri = $ruote_properties['broker_uri']

      $logger.debug('Executing ResourceMonitorParticipant [resourceId={}]', resource_id)

      raise 'resource_id is not set' unless defined? resource_id and not resource_id.nil?
      raise 'message_producer not defined' unless defined? producer
      raise 'broker_uri not defined' unless defined? broker_uri

      uri = broker_uri.resolve('resource-monitor')
      message = ResourceMonitorMessage.new(resource_id)

      $logger.debug('Sending resource monitor message [uri={}, message={}]', uri, message)

      producer.send(uri, message).get()

      reply
    end
  end
end
