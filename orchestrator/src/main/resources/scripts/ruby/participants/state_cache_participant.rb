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

class RuoteStateChangeCallback < org.cloudifysource.cosmo.statecache.StateChangeCallbackStub

  NODE = 'node'
  RUNTIME = 'cloudify_runtime'
  @resource_id = nil

  def resource_id=(resource_id)
    @resource_id = resource_id
  end

  def onStateChange(participant, workitem, cache, new_snapshot)
    matches = false
    $logger.debug('RuoteStateChangeCallback invoked: [resource_id={}, params={}, snapshot={}]',
                  @resource_id, workitem.params, new_snapshot)

    state = new_snapshot.get(@resource_id)
    raise "state is not of type map #{state.get_class}" unless state.java_kind_of?(java::util::Map)
    required_state = workitem.params[StateCacheParticipant::STATE]
    $logger.debug('RuoteStateChangeCallback checking state: [state={}, required_state={}]',
                  state, required_state)
    required_state.each do |key, value|
      matches = (state.contains_key(key) and state.get(key).to_s.eql? value.to_s)
      break unless matches
    end


    if matches
      if workitem.fields.has_key? NODE
        current_node = workitem.fields[NODE]
        node_state = Hash.new
        state.each { |key, value| node_state[key] = value }
        properties = current_node['properties']

        # state cache listener is always invoked by a single thread
        # and therefore the following code is safe
        properties[RUNTIME] = Hash.new unless properties.has_key? RUNTIME
        properties[RUNTIME][@resource_id] = node_state
      else
        workitem.fields.merge!(new_snapshot)
      end
      participant.reply(workitem)
      true
    else
      false
    end
  end

end

class StateCacheParticipant < Ruote::Participant

  STATE = 'state'
  def on_workitem
    begin
      state_cache = $ruote_properties['state_cache']
      resource_id = workitem.params['resource_id']
      raise 'state_cache property is not set' unless defined? state_cache
      raise 'resource_id property is not set' unless defined? resource_id
      raise "#{STATE} parameter is not defined for state cache participant" unless workitem.params.has_key? STATE

      callback = RuoteStateChangeCallback.new
      callback.resource_id = resource_id
      callback_uid = state_cache.subscribe_to_key_value_state_changes(self,
                                                                      workitem,
                                                                      resource_id,
                                                                      callback)
      $logger.debug('StateCacheParticipant: subscribed with [resource_id={}]', resource_id)
      put('callback_uid', callback_uid)
    rescue Exception => e
      $logger.debug(e.message)
      raise e
    end
  end

  def on_cancel
    begin
      state_cache = $ruote_properties['state_cache']
      callback_uid = get('callback_uid')
      state_cache.remove_callback(callback_uid)
    rescue Exception => e
      $logger.debug(e.message)
      raise
    end
  end

  def do_not_thread
    true
  end

end
