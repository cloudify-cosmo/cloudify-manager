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
  NODE_OPERATION = 'node_operation'
  OPERATION_MAPPING = 'operation_mapping'
  OPERATION_PROPERTIES = 'operation_properties'
  OPERATIONS = 'operations'
  SOURCE_OPERATIONS = 'source_operations'
  TARGET_OPERATIONS = 'target_operations'
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
        raise "#{RUN_ON_NODE} parameter not set" unless workitem.params.has_key? RUN_ON_NODE
        run_on_node = workitem.params[RUN_ON_NODE]
        relationship = workitem.params[RELATIONSHIP]
        target_id = relationship[TARGET_ID]

        raise "Relationship [#{relationship}] missing target_id" if target_id.nil? or target_id.empty?

        source_node = workitem.fields[NODE]
        target_node = workitem.fields[PLAN][NODES].find {|node| node[NODE_ID] == target_id }
        workitem.fields[RELATIONSHIP_OTHER_NODE] = target_node

        raise "Node missing with id #{target_id}" if target_node.nil?

        if run_on_node == 'source'
          node = source_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = target_node[NODE_ID]
          operations = relationship[SOURCE_OPERATIONS]
        elsif run_on_node == 'target'
          node = target_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = source_node[NODE_ID]
          operations = relationship[TARGET_OPERATIONS]
        else
          raise "Invalid bind location specified for relationship[#{relationship}]: #{run_on_node}"
        end
      else
        # cleanup
        workitem.fields.delete(RUOTE_RELATIONSHIP_NODE_ID)
        workitem.fields.delete(RELATIONSHIP_OTHER_NODE)

        node = workitem.fields[NODE]
        operations = node[OPERATIONS]
      end
      if operations.nil? || operations[operation].nil?
        workitem.fields[OPERATION] = 'no_op'
        reply
        return
      end

      raise "Node is missing a #{PLUGINS} property" unless node.has_key? PLUGINS
      op_struct = operations[operation]
      plugin_name = op_struct['plugin']
      operation_mapping = op_struct['operation']
      operation_properties = nil
      if op_struct.has_key? 'properties'
        operation_properties = op_struct['properties']
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
      workitem.fields[PLUGIN_NAME] = plugin_name
      workitem.fields[OPERATION] = "#{workitem.fields[PLUGIN_NAME]}.#{operation_mapping}"
      workitem.fields[NODE_OPERATION] = operation

      if operation_properties.nil?
        workitem.fields[OPERATION_PROPERTIES] = workitem.fields[NODE][PreparePlanParticipant::PROPERTIES]
      else
        if workitem.fields[NODE][PreparePlanParticipant::PROPERTIES].has_key? PreparePlanParticipant::RUNTIME
          operation_properties[PreparePlanParticipant::RUNTIME] =
              workitem.fields[NODE][PreparePlanParticipant::PROPERTIES][PreparePlanParticipant::RUNTIME]
        end
        workitem.fields[OPERATION_PROPERTIES] = operation_properties
      end
      reply

    rescue => e
      log_exception(e, 'prepare_operation')
      flunk(workitem, e)
    end
  end

end
