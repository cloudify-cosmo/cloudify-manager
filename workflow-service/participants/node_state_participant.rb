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


require 'rest_client'
require 'json'
require 'uri'
require 'set'


######
# Participant getting/waiting to/for node reachable state.
# If there's a node in context, by default node runtime state will be read from storage and injected
# to the node in context (usually relevant when there are relationships between nodes).
#
class NodeStateParticipant < Ruote::Participant

  NODE_ID = 'node_id'
  MATCHES_FIELD_PARAM_NAME = 'to_f'
  MANAGER_REST_BASE_URI = 'MANAGER_REST_BASE_URI'
  REACHABLE = 'reachable'
  NODE = 'node'
  ACTION = 'action'
  WAIT = 'wait'
  VALID_ACTIONS = [WAIT, 'get'].to_set

  def on_workitem
    begin
      # TODO runtime-model: handle exceptions in a smart way which will fail the entire workflow if exception is not related to 'matches' logic.
      # TODO runtime-model: pass manager rest base uri as ENV variable
      ENV[MANAGER_REST_BASE_URI] = 'http://localhost:8100'

      raise "#{NODE_ID} property is not set" unless (workitem.params[NODE_ID] || '').length > 0
      raise "#{MANAGER_REST_BASE_URI} is not set in ruby env" unless ENV.has_key? MANAGER_REST_BASE_URI

      action = workitem.params[ACTION] || WAIT
      raise "invalid action: #{action} - available actions: #{VALID_ACTIONS}" unless VALID_ACTIONS.include? action
      wait_until_matches = false
      if action.eql? WAIT
        wait_until_matches = true
        raise "#{REACHABLE} parameter is not defined for node state participant" unless (workitem.params[REACHABLE] || '').length > 0
      end

      base_uri = ENV[MANAGER_REST_BASE_URI]
      node_id = workitem.params[NODE_ID]
      current_node = workitem.fields[PreparePlanParticipant::NODE] || nil
      result_field = workitem.params[MATCHES_FIELD_PARAM_NAME] || nil

      $logger.debug('Node state participant called [context={}, action={}, node_id={}, value={}, result_field={}]',
                    current_node['id'] || nil,
                    action,
                    node_id,
                    workitem.params[REACHABLE],
                    result_field)

      # TODO runtime-model: handle HTTP status codes and connection errors

      url = URI::escape("#{base_uri}/nodes/#{node_id}?reachable=true&runtime=#{wait_until_matches and not current_node.nil?}")
      response = RestClient.get(url)
      node_state = JSON.parse(response.to_str)

      reachable = node_state[REACHABLE]

      if wait_until_matches
        requested_reachable_state = workitem.params[REACHABLE]
        matches = requested_reachable_state.to_s.eql? reachable.to_s

        raise "node reachable state does not match [requested=#{requested_reachable_state}, actual=#{reachable}" if wait_until_matches and not matches

        # if there's a node in context, inject the requested node's runtime state
        if requested_reachable_state and not current_node.nil?
          if node_state.has_key? 'runtimeInfo'
            current_node = workitem.fields[PreparePlanParticipant::NODE]
            properties = current_node[PreparePlanParticipant::PROPERTIES]
            properties[PreparePlanParticipant::RUNTIME][node_id] = node_state['runtimeInfo']
          end
        end
      elsif not result_field.nil?
          $logger.debug('Node reachable state is set as \'{}\' workitem field [state={}]', result_field, reachable)
          workitem.fields[result_field] = reachable
      end

      reply

    rescue => e
      log_exception(workitem, e, 'node_state')
      flunk(workitem, e)
    end
  end

  def do_not_thread
    false
  end


end
