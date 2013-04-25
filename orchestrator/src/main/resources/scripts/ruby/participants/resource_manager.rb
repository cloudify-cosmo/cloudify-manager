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

class ResourceManagerParticipant < Ruote::Participant
  def on_workitem
    begin
      action = workitem.params['action']
      producer = $ruote_properties['message_producer']
      broker_uri = $ruote_properties['broker_uri']

      puts "executing resource_manager_participant [action=#{action}, broker_uri=#{broker_uri}]"

      raise "unknown action '#{action}'" if action != 'start_machine'
      raise 'message_producer not defined' unless defined? producer
      raise 'broker_uri not defined' unless defined? broker_uri
      uri = broker_uri.resolve('/resource-manager')
      producer.send(uri, action)
      reply
    end
  end
end
