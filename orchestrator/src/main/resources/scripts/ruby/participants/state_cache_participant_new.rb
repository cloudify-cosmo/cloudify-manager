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

class RuoteStateChangeListener < org.cloudifysource.cosmo.statecache.StateCacheListenerStub

  NODE = 'node'
  RUNTIME = 'cloudify_runtime'
  PROPERTIES = 'properties'

  @participant = nil
  @resource_id = nil
  @parameters = nil
  @fields = nil
  @workitem = nil

  def resource_id=(participant, resource_id, workitem)
    @participant = participant
    @resource_id = resource_id
    @workitem = workitem

    $logger.debug('RuoteStateChangeListener created: [resource_id={}, parameters={}]',
                  @resource_id, @workitem.params)
  end

  def onResourceStateChange(snapshot)
    matches = false

    required_state = @workitem.params[StateCacheParticipant::STATE]

    $logger.debug('RuoteStateChangeCallback checking state: [resource_id={}, parameters={}, snapshot={},
required_state={}]', @resource_id, @workitem.params, snapshot, required_state)
    required_state.each do |key, value|
      matches = (snapshot.contains_property(@resource_id, key) and snapshot.get_property(@resource_id,
                                                                                 key).to_s.eql? value.to_s)
      break unless matches
    end


    if matches
      if @workitem.fields.has_key? NODE
        current_node = @workitem.fields[NODE]
        state = snapshot.get_resource_properties(@resource_id)
        node_state = Hash.new
        state.each { |key, value| node_state[key] = value }
        properties = current_node[PROPERTIES]

        # state cache listener is always invoked by a single thread
        # and therefore the following code is safe
        properties[RUNTIME] = Hash.new unless properties.has_key? RUNTIME
        properties[RUNTIME][@resource_id] = node_state
      end
      @participant.reply(@workitem)
      true
    else
      false
    end
  end

end

class StateCacheParticipant < Ruote::Participant


  STATE_CACHE = 'state_cache'
  RESOURCE_ID = 'resource_id'
  LISTENER = 'listener'
  STATE = 'state'

  def on_workitem
    begin
      state_cache = $ruote_properties[STATE_CACHE]
      resource_id = workitem.params[RESOURCE_ID]
      raise "#{STATE_CACHE} state_cache property is not set" unless defined? state_cache
      raise "#{RESOURCE_ID} property is not set" unless defined? resource_id
      raise "#{STATE} parameter is not defined for state cache participant" unless workitem.params.has_key? STATE

      listener = RuoteStateChangeListener.new(self, resource_id, workitem)
      state_cache.subscribe(resource_id, listener)
      $logger.debug('StateCacheParticipant: subscribed with [resource_id={}]', resource_id)
      put(LISTENER, listener)
    rescue Exception => e
      $logger.debug(e.message)
      raise e
    end
  end

  def on_cancel
    begin
      state_cache = $ruote_properties[STATE_CACHE]
      listener = get(LISTENER)
      state_cache.remove_subscription(workitem.params[RESOURCE_ID], listener)
    rescue Exception => e
      $logger.debug(e.message)
      raise
    end
  end

  def do_not_thread
    true
  end

end
