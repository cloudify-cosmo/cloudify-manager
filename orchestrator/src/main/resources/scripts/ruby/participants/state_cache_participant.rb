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

java_import org.cloudifysource::cosmo::statecache::StateCacheListener
require 'json'

class StateCacheParticipant < Ruote::Participant
  include StateCacheListener

  STATE_CACHE = 'state_cache'
  RESOURCE_ID = 'resource_id'
  LISTENER_ID = 'listener_id'
  STATE = 'state'

  def on_workitem
    begin
      state_cache = $ruote_properties[STATE_CACHE]
      resource_id = workitem.params[RESOURCE_ID]
      raise "#{STATE_CACHE} state_cache property is not set" unless defined? state_cache
      raise "#{RESOURCE_ID} property is not set" unless defined? resource_id
      raise "#{STATE} parameter is not defined for state cache participant" unless workitem.params.has_key? STATE

      listener_id = state_cache.subscribe(resource_id, self)
      $logger.debug('StateCacheParticipant: subscribed with [resource_id={}, workitem={}]', resource_id, workitem)
      put(LISTENER_ID, listener_id)
    rescue Exception => e
      $logger.debug(e.message)
      raise e
    end
  end

  def on_cancel
    begin
      state_cache = $ruote_properties[STATE_CACHE]
      listener_id = get(LISTENER_ID)
      state_cache.remove_subscription(workitem.params[RESOURCE_ID], listener_id)
    rescue Exception => e
      $logger.debug(e.message)
      raise
    end
  end

  def do_not_thread
    true
  end

  def onResourceStateChange(snapshot)
    matches = false
    resource_id = workitem.params[RESOURCE_ID]
    required_state = workitem.params[STATE]

    $logger.debug('StateCacheParticipant onResourceStateChange called, checking state: [resource_id={}, parameters={},
snapshot={},
required_state={}]', resource_id, workitem.params, snapshot, required_state)
    required_state.each do |key, value|
      matches = (snapshot.contains_property(resource_id, key) and
          snapshot.get_property(resource_id, key).get.get_state.to_s.eql? value.to_s)
      break unless matches
    end


    if matches
      if workitem.fields.has_key? PreparePlanParticipant::NODE
        current_node = workitem.fields[PreparePlanParticipant::NODE]
        state = snapshot.get_resource_properties(resource_id)
        node_state = Hash.new
        state.each do |key, value|
          node_state[key] = value.get_state
          unless value.get_description.to_s == ''
            description = JSON.parse(value.get_description)
            description['state'] = value.get_state
            $logger.debug('[event] {}', JSON.generate(description))
          end
        end
        properties = current_node[PreparePlanParticipant::PROPERTIES]
        properties[PreparePlanParticipant::RUNTIME][resource_id] = node_state
      end
      reply(workitem)
      true
    else
      false
    end
  end

end
