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

  @resource_id = nil

  def resource_id=(resource_id)
    @resource_id = resource_id
  end

  def onStateChange(participant, workitem, cache, new_snapshot)
    matches = true
    unless @resource_id.nil?
      state = new_snapshot.get(@resource_id)
      if state.java_kind_of?(java::util::Map)
        workitem.params.each do |key, value|
          if key != 'resource_id' and key != 'ref'
            matches = (state.contains_key(key) and state.get(key).to_s.eql? value.to_s)
          end
          break unless matches
        end
      end
    end
    $logger.debug('RuoteStateChangeCallback invoked: [params={}, snapshot={}, matches={}]',
                  workitem.params, new_snapshot, matches)
    if matches
      workitem.fields.merge!(new_snapshot)
      participant.reply(workitem)
    end
  end

end

class StateCacheParticipant < Ruote::Participant

  def on_workitem
    begin
      state_cache = $ruote_properties['state_cache']
      raise 'state_cache property is not set' unless defined? state_cache

      resource_id = workitem.params['resource_id']
      resource_id = nil unless defined? resource_id

      if resource_id.nil?
        condition_key = workitem.params['key']
        condition_value = workitem.params['value']
        raise 'key parameter is not defined for state cache participant' unless defined? condition_key and not
          condition_key.to_s.empty?
        raise 'value parameter is not defined for state cache participant' unless defined? condition_value and not
          condition_value.to_s.empty?
        callback = RuoteStateChangeCallback.new
        callback_uid = state_cache.subscribe_to_key_value_state_changes(self,
                                                                        workitem,
                                                                        condition_key,
                                                                        condition_value,
                                                                        callback)
        $logger.debug('StateCacheParticipant: subscribed with [key={}, value={}]', condition_key, condition_value)
      else
        callback = RuoteStateChangeCallback.new
        callback.resource_id = resource_id
        callback_uid = state_cache.subscribe_to_key_value_state_changes(self,
                                                                        workitem,
                                                                        resource_id,
                                                                        callback)
        $logger.debug('StateCacheParticipant: subscribed with [resource_id={}]', resource_id)
      end

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
