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


class NodeStateParticipant < Ruote::Participant

  NODE_ID = 'node_id'
  WAIT_UNTIL_MATCHES = 'wait_until_matches'
  MATCHES_FIELD_PARAM_NAME = 'to_f'
  MANAGER_REST_BASE_URI = 'MANAGER_REST_BASE_URI'
  REACHABLE = 'reachable'
  NODE = 'node'

  def on_workitem
    begin
      # TODO runtime-model: pass manager rest base uri as ENV variable
      ENV[MANAGER_REST_BASE_URI] = 'http://localhost:8100'

      node_id = workitem.params[NODE_ID]
      raise "#{NODE_ID} property is not set" unless defined? node_id
      raise "#{REACHABLE} parameter is not defined for node state  participant" unless workitem.params.has_key? REACHABLE
      raise "#{MANAGER_REST_BASE_URI} is not set in ruby env" unless ENV.has_key? MANAGER_REST_BASE_URI

      base_uri = ENV[MANAGER_REST_BASE_URI]

      # TODO runtime-model: handle HTTP status codes and connection errors
      response = RestClient.get "#{base_uri}/nodes/#{node_id}?reachable"
      processed = JSON.parse(response.to_str)

      requested_reachable_state = workitem.params[REACHABLE]
      reachable = processed[REACHABLE]

      matches = requested_reachable_state.to_s.eql? reachable.to_s

      wait_until_matches = workitem.params[WAIT_UNTIL_MATCHES] || true

      raise 'node reachable state does not match' if wait_until_matches and not matches

      if workitem.params.has_key? MATCHES_FIELD_PARAM_NAME
        workitem.fields[workitem.params[MATCHES_FIELD_PARAM_NAME]] = matches
      end

      if requested_reachable_state and workitem.fields.has_key? PreparePlanParticipant::NODE
        # TODO runtime-model: handle HTTP status codes and connection errors
        response = RestClient.get "#{base_uri}/nodes/#{node_id}"
        node_state = JSON.parse(response.to_str)
        if node_state.has_key? 'runtimeInfo'
          current_node = workitem.fields[PreparePlanParticipant::NODE]
          properties = current_node[PreparePlanParticipant::PROPERTIES]
          properties[PreparePlanParticipant::RUNTIME][node_id] = node_state['runtimeInfo']
        end
      end

      reply

    rescue => e
      log_exception(e, 'node_state')
      flunk(workitem, e)
    end
  end

  def do_not_thread
    true
  end


end
