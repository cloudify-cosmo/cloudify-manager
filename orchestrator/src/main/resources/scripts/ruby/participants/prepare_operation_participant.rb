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

require_relative '../exception_logger'

class PrepareOperationParticipant < Ruote::Participant

  PLAN = 'plan'
  NODES = 'nodes'
  RELATIONSHIP = 'relationship'
  RELATIONSHIPS = 'relationships'
  TARGET_ID = 'target_id'
  NODE_ID = 'id'
  RELATIONSHIP_OTHER_NODE = 'relationship_other_node'
  RUOTE_RELATIONSHIP_NODE_ID = 'relationship_node_id'
  RUN_LOCATION = 'run_location'
  TYPE = 'type'
  INTERFACE_IMPLEMENTATION = 'interface_implementation'

  NODE = 'node'
  OPERATION = 'operation'
  OPERATIONS = 'operations'
  TARGET = 'target'
  PLUGINS = 'plugins'
  AGENT_PLUGIN = 'agent_plugin'
  HOST_ID = 'host_id'
  CLOUDIFY_MANAGEMENT = 'cloudify.management'
  PLUGIN_NAME = 'plugin_name'
  WORKER_ID = 'worker_id'

  def on_workitem
    begin
      raise "#{PLAN} field not set" unless workitem.fields.has_key? PLAN
      raise "#{NODE} field not set" unless workitem.fields.has_key? NODE
      raise "#{OPERATION} parameter not set" unless workitem.params.has_key? OPERATION

      operation = workitem.params[OPERATION]

      relationship_operation = (workitem.params.has_key? RELATIONSHIP and not workitem.params[RELATIONSHIP].nil?)
      if relationship_operation
        relationship = workitem.params[RELATIONSHIP]
        target_id = relationship[TARGET_ID]
        run_location = relationship[RUN_LOCATION]
        relationship_type = relationship[TYPE]
        plugin_name = relationship[INTERFACE_IMPLEMENTATION]

        raise "Relationship [#{relationship}] missing target_id" if target_id.nil? or target_id.empty?
        raise "Relationship [#{relationship}] missing run_location" if run_location.nil? or run_location.empty?
        raise "Relationship [#{relationship}] missing type" if relationship_type.nil? or relationship_type.empty?
        raise "Relationship [#{relationship}] missing interface_implementation" if relationship_type.nil? or relationship_type.empty?

        source_node = workitem.fields[NODE]
        target_node = workitem.fields[PLAN][NODES].find {|node| node[NODE_ID] == target_id }
        workitem.fields[RELATIONSHIP_OTHER_NODE] = target_node

        raise "Node missing with id #{target_id}" if target_node.nil?

        if run_location == 'source'
          node = source_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = target_node[NODE_ID]
        elsif run_location == 'target'
          node = target_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = source_node[NODE_ID]
        else
          raise "Invalid run location specified for relationship[#{relationship}]: #{run_location}"
        end
      else
        node = workitem.fields[NODE]
        workitem.fields[RELATIONSHIP_OTHER_NODE] = nil

        operations = node[OPERATIONS]
        raise "Node has no operations: #{node}" unless operations != nil
        raise "Node is missing a #{PLUGINS} property" unless node.has_key? PLUGINS
        raise "No such operation '#{operation}' for node: #{node}" unless operations.has_key? operation
        plugin_name = operations[operation]
      end

      $logger.debug('Executing operation [operation={}, plugin={}]', operation, plugin_name)

      workitem.fields[TARGET] = CLOUDIFY_MANAGEMENT
      workitem.fields[PLUGIN_NAME] = "cosmo.#{plugin_name}.tasks"
      workitem.fields[WORKER_ID] = 'celery.cloudify.management'
      if node[PLUGINS][plugin_name][AGENT_PLUGIN].to_s.eql? 'true'
        raise 'node does not contain a host_id property' unless node.has_key? HOST_ID
        workitem.fields[TARGET] = node[HOST_ID]
        workitem.fields[WORKER_ID] = "celery.#{node[HOST_ID]}"
      end
      # operation can have the interface name as its prefix: 'control.start' or just 'start'
      workitem.fields[OPERATION] = "cosmo.#{plugin_name}.tasks.#{operation.split('.')[-1]}"

      reply

    rescue => e
      log_exception(e, 'prepare_operation')
      flunk(workitem, e)
    end
  end

end
