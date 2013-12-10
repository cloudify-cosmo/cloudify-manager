#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
#

java_import org.cloudifysource::cosmo::statecache::StateCacheListener
require 'json'
require_relative 'exception_logger'

class StateCacheParticipant < Ruote::Participant
  include StateCacheListener

  STATE_CACHE = 'state_cache'
  RESOURCE_ID = 'resource_id'
  WAIT_UNTIL_MATCHES = 'wait_until_matches'
  MATCHES_FIELD_PARAM_NAME = 'to_f'
  LISTENER_ID = 'listener_id'
  STATE = 'state'
  NODE = 'node'

  def on_workitem
    begin
      state_cache = $ruote_properties[STATE_CACHE]
      resource_id = workitem.params[RESOURCE_ID]
      raise "#{STATE_CACHE} state_cache property is not set" unless defined? state_cache
      raise "#{RESOURCE_ID} property is not set" unless defined? resource_id
      raise "#{STATE} parameter is not defined for state cache participant" unless workitem.params.has_key? STATE

      listener_id = state_cache.subscribe(resource_id, self)
      node_that_is_waiting = workitem.fields[NODE] || {}
      node_id_that_is_waiting = node_that_is_waiting['id'] || ""

      $logger.debug('StateCacheParticipant: subscribed with [resource_id={}, node_id_that_is_waiting={}, params={}]',
      resource_id, node_id_that_is_waiting, workitem.params)
      put(LISTENER_ID, listener_id)
    rescue => e
      log_exception(e, 'state_cache')
      flunk(workitem, e)
    end
  end

  def on_cancel
    begin
      state_cache = $ruote_properties[STATE_CACHE]
      listener_id = get(LISTENER_ID)
      state_cache.remove_subscription(workitem.params[RESOURCE_ID], listener_id)
    rescue => e
      log_exception(e, 'state_cache')
      flunk(workitem, e)
    end
  end

  def do_not_thread
    true
  end

  def onResourceStateChange(snapshot)
    begin
        matches = false
        resource_id = workitem.params[RESOURCE_ID]
        required_state = workitem.params[STATE]
        node_that_is_waiting = workitem.fields[NODE] || {}
        node_id_that_is_waiting = node_that_is_waiting['id'] || ""
        wait_until_matches = if workitem.params.has_key? WAIT_UNTIL_MATCHES;
                               workitem.params[WAIT_UNTIL_MATCHES]
                             else
                               true
                             end

        $logger.debug('StateCacheParticipant onResourceStateChange called,
                      checking state: [resource_id={}, parameters={}, snapshot={}, required_state={},
                      node_id_that_is_waiting={}, wait_until_matches={}]',
                      resource_id, workitem.params, snapshot, required_state, node_id_that_is_waiting, wait_until_matches)

        required_state.each do |key, value|
          matches = (snapshot.contains_property(resource_id, key) and
              snapshot.get_property(resource_id, key).get.get_state.to_s.eql? value.to_s)
          break unless matches
        end


        if matches or not wait_until_matches
          if workitem.fields.has_key? PreparePlanParticipant::NODE
            current_node = workitem.fields[PreparePlanParticipant::NODE]
            state = snapshot.get_resource_properties(resource_id)
            node_state = Hash.new

            state.each do |key, value|
              node_state[key] = value.get_state
              unless value.get_description.to_s == ''
                description = JSON.parse(value.get_description)
                description['state'] = value.get_state
                description['wfid'] = workitem.wfid
                description['service'] = key
                $logger.debug('[event] {}', JSON.generate(description))
              end
            end

            properties = current_node[PreparePlanParticipant::PROPERTIES]
            properties[PreparePlanParticipant::RUNTIME][resource_id] = node_state
          end
          if workitem.params.has_key? MATCHES_FIELD_PARAM_NAME
            workitem.fields[workitem.params[MATCHES_FIELD_PARAM_NAME]] = matches
          end
          reply(workitem)
          true
        else
          false
        end
    rescue => e
      log_exception(e, 'state_cache')
      flunk(workitem, e)
    end
  end

end
