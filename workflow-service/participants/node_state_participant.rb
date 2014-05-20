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
require_relative '../utils/logs'

######
# Participant getting/waiting to/for node state.
# If there's a node in context, by default node runtime state will be read from storage and injected
# to the node in context (usually relevant when there are relationships between nodes).
#
class NodeStateParticipant < Ruote::Participant

  NODE_ID = 'node_id'
  MATCHES_FIELD_PARAM_NAME = 'to_f'
  MANAGER_REST_BASE_URI = 'MANAGER_REST_BASE_URI'
  VALUE = 'value'
  NODE = 'node'
  ACTION = 'action'
  WAIT = 'wait'
  SET = 'set'
  GET = 'get'
  VALID_ACTIONS = [WAIT, GET, SET].to_set

  def do_not_thread
    false
  end

  def on_workitem
    begin
      # TODO runtime-model: handle exceptions in a smart way which will fail the entire workflow if exception is not related to 'matches' logic.
      # TODO runtime-model: pass manager rest base uri as ENV variable
      ENV[MANAGER_REST_BASE_URI] = 'http://localhost:8100'

      raise "#{NODE_ID} property is not set" unless (workitem.params[NODE_ID] || '').length > 0
      raise "#{MANAGER_REST_BASE_URI} is not set in ruby env" unless ENV.has_key? MANAGER_REST_BASE_URI

      action = workitem.params[ACTION] || WAIT
      raise "invalid action: #{action} - available actions: #{VALID_ACTIONS}" unless VALID_ACTIONS.include? action

      if action.eql? SET
        set_node_state
        return
      end


      wait_until_matches = false
      if action.eql? WAIT
        wait_until_matches = true
        raise "#{VALUE} parameter is not defined for node state participant" unless (workitem.params[VALUE] || '').length > 0
      end

      base_uri = ENV[MANAGER_REST_BASE_URI]
      node_id = workitem.params[NODE_ID]
      current_node = workitem.fields[PreparePlanParticipant::NODE] || nil
      result_field = workitem.params[MATCHES_FIELD_PARAM_NAME] || nil

      log(:debug, "Node state participant called [context=#{current_node['id'] || nil}, action=#{action}, node_id=#{node_id}, value=#{workitem.params[VALUE]}, result_field=#{result_field}]", {
          :workitem => workitem
      })

      # TODO runtime-model: handle HTTP status codes and connection errors

      url = URI::escape("#{base_uri}/nodes/#{node_id}?state_and_runtime_properties=true")
      response = RestClient.get(url)
      node_state = JSON.parse(response.to_str)

      actual_state = node_state['state']

      if wait_until_matches
        requested_state = workitem.params[VALUE]
        matches = requested_state.to_s.eql? actual_state.to_s
        unless result_field.nil?
          workitem.fields[result_field] = matches
        end

        if matches
          # if there's a node in context, inject the requested node's runtime state
          if requested_state and not current_node.nil?
            if node_state.has_key? 'runtimeInfo'
              current_node = workitem.fields[PreparePlanParticipant::NODE]
              properties = current_node[PreparePlanParticipant::PROPERTIES]
              properties[PreparePlanParticipant::RUNTIME][node_id] = node_state['runtimeInfo']
            end
          end
        elsif result_field.nil?
          raise "node state does not match [requested=#{requested_state}, actual=#{actual_state}"
        end

      elsif not result_field.nil?
        log(:debug, "Node state is set as '#{result_field}' workitem field [state=#{actual_state}]", {
            :workitem => workitem
        })
        workitem.fields[result_field] = actual_state
      end

      log(:debug, "Wait for node state result [action=#{action}, node_id=#{node_id}, matches=#{matches}, requested_value=#{requested_state}, result_field=#{result_field}", {
          :workitem => workitem
      })

      reply

    rescue => e
      log_exception(workitem, e, 'node_state')
      flunk(workitem, e)
    end
  end

  def set_node_state
    raise "Required parameter 'value' for set action is missing" unless workitem.params.has_key? 'value'
    node_id = workitem.params[NODE_ID]
    value = workitem.params['value']

    log(:debug, "Setting node: #{node_id} as '#{value}'", {
        :workitem => workitem
    })

    base_uri = 'http://localhost:8100'

    url = URI::escape("#{base_uri}/nodes/#{node_id}?state_and_runtime_properties=true")
    response = RestClient.get(url)
    state_version = JSON.parse(response.to_str)['stateVersion']

    url = URI::escape("#{base_uri}/nodes/#{node_id}")
    body = JSON.generate({
        :state_version => state_version,
        :state => value
                         })
    RestClient.patch url, body, {:content_type => :json}

    reply
  end

end
