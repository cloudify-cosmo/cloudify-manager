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

require_relative 'exception_logger'

class PrepareOperationParticipant < Ruote::Participant

  PLAN = 'plan'
  NODES = 'nodes'
  RELATIONSHIP = 'relationship'
  RELATIONSHIPS = 'relationships'
  TARGET_ID = 'target_id'
  NODE_ID = 'id'
  RELATIONSHIP_OTHER_NODE = 'relationship_other_node'
  RUOTE_RELATIONSHIP_NODE_ID = 'relationship_node_id'
  RUN_ON_NODE = 'run_on_node'
  TYPE = 'type'
  PLUGIN = 'plugin'

  NODE = 'node'
  OPERATION = 'operation'
  OPERATION_MAPPING = 'operation_mapping'
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
        run_on_node = relationship[RUN_ON_NODE]
        plugin_name = relationship[PLUGIN]
        operation_mapping = 'none'

        raise "Relationship [#{relationship}] missing target_id" if target_id.nil? or target_id.empty?
        raise "Relationship [#{relationship}] missing run_on_node" if run_on_node.nil? or run_on_node.empty?
        raise "Relationship [#{relationship}] missing plugin" if plugin_name.nil? or plugin_name.empty?

        source_node = workitem.fields[NODE]
        target_node = workitem.fields[PLAN][NODES].find {|node| node[NODE_ID] == target_id }
        workitem.fields[RELATIONSHIP_OTHER_NODE] = target_node

        raise "Node missing with id #{target_id}" if target_node.nil?

        if run_on_node == 'source'
          node = source_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = target_node[NODE_ID]
        elsif run_on_node == 'target'
          node = target_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = source_node[NODE_ID]
        else
          raise "Invalid bind location specified for relationship[#{relationship}]: #{run_on_node}"
        end
      else
        node = workitem.fields[NODE]
        workitem.fields.delete(RELATIONSHIP_OTHER_NODE)
        workitem.fields.delete(RUOTE_RELATIONSHIP_NODE_ID)

        operations = node[OPERATIONS]
        raise "Node has no operations: #{node}" unless operations != nil
        raise "Node is missing a #{PLUGINS} property" unless node.has_key? PLUGINS
        raise "No such operation '#{operation}' for node: #{node}" unless operations.has_key? operation
        op_struct = operations[operation]
        plugin_name = op_struct['plugin']
        operation_mapping = op_struct['operation']
      end

      $logger.debug('Executing operation [operation={}, plugin={}, operation_mapping={}]',
                    operation, plugin_name, operation_mapping)

      workitem.fields[TARGET] = CLOUDIFY_MANAGEMENT
      if node[PLUGINS][plugin_name][AGENT_PLUGIN].to_s.eql? 'true'
        raise 'node does not contain a host_id property' unless node.has_key? HOST_ID
        workitem.fields[TARGET] = node[HOST_ID]
      end
      workitem.fields[WORKER_ID] = "celery.#{workitem.fields[TARGET]}"
      workitem.fields[OPERATION_MAPPING] = operation_mapping
      workitem.fields[PLUGIN_NAME] = "cosmo.#{plugin_name}"
      workitem.fields[OPERATION] = "#{workitem.fields[PLUGIN_NAME]}.#{operation_mapping}"

      reply

    rescue => e
      log_exception(e, 'prepare_operation')
      flunk(workitem, e)
    end
  end

end
