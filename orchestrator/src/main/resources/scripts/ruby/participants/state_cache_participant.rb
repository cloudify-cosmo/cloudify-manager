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

class RuoteStateChangeCallback < org.cloudifysource.cosmo.statecache.StateChangeCallbackStub

  def onStateChange(participant, workitem, cache, new_snapshot)
    workitem.fields.merge!(new_snapshot)
    participant.reply(workitem)
  end

end

class StateCacheParticipant < Ruote::Participant

  def on_workitem
    begin
      state_cache = $ruote_properties['state_cache']
      condition_key = workitem.params['key']
      condition_value = workitem.params['value']
      resource_id = workitem.params['resource_id']

      raise 'state_cache property is not set' unless defined? state_cache
      raise 'key parameter is not defined for state cache participant' unless defined? condition_key and not
        condition_key.to_s.empty?
      raise 'value parameter is not defined for state cache participant' unless defined? condition_value and not
        condition_value.to_s.empty?

      if defined? resource_id and not resource_id.to_s.empty?
        condition_key = "#{resource_id}.#{condition_key}"
      end

      callback = RuoteStateChangeCallback.new
      callback_uid = state_cache.subscribe_to_key_value_state_changes(self,
                                                                      workitem,
                                                                      condition_key,
                                                                      condition_value,
                                                                      callback)
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
