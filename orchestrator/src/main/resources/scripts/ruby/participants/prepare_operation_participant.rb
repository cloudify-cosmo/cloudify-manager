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

class PrepareOperationParticipant < Ruote::Participant

  PLAN = 'plan'
  NODES = 'nodes'
  TARGET_ID = 'target_node_id'
  NODE_ID = 'id'
  SOURCE_PREFIX = 'source.'
  TARGET_PREFIX = 'target.'
  RELATIONSHIP_OTHER_NODE = 'relationship_other_node'
  RUOTE_RELATIONSHIP_NODE_ID = 'relationship_node_id'

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
      raise "#{NODE} field not set" unless workitem.fields.has_key? NODE
      raise "#{OPERATION} parameter not set" unless workitem.params.has_key? OPERATION

      operation = workitem.params[OPERATION]

      allow_dynamic_operations = false
      if workitem.params.has_key? TARGET_ID and workitem.params[TARGET_ID] != ''
        allow_dynamic_operations = true
        target_id = workitem.params[TARGET_ID]
        source_node = workitem.fields[NODE]
        target_node = workitem.fields[PLAN][NODES].find {|node| node[NODE_ID] == target_id }
        workitem.fields[RELATIONSHIP_OTHER_NODE] = target_node
        raise "Node missing with id #{target_id}" if target_node.nil?
        if operation.start_with? SOURCE_PREFIX
          operation = operation[SOURCE_PREFIX.length, operation.length]
          node = source_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = target_node[NODE_ID]
        elsif operation.start_with? TARGET_PREFIX
          operation = operation[TARGET_PREFIX.length, operation.length]
          node = target_node
          workitem.fields[RUOTE_RELATIONSHIP_NODE_ID] = source_node[NODE_ID]
        else
          raise "Invalid execution destination specified in operation: #{operation}"
        end
      else
        node = workitem.fields[NODE]
        workitem.fields[RELATIONSHIP_OTHER_NODE] = nil
      end

      operations = node[OPERATIONS]
      raise "Node has no operations: #{node}" unless operations != nil
      raise "Node is missing a #{PLUGINS} property" unless node.has_key? PLUGINS

      if allow_dynamic_operations
        if operations.has_key? operation
          plugin_name = operations[operation]
        else
          split_op = operation.split('.')
          operation = split_op[-1]
          plugin_name = split_op[0, split_op.length - 1].join('.')
          raise "Node does not have a plugin named: #{plugin_name}" unless node[PLUGINS].has_key? plugin_name
        end
      else
        raise "No such operation '#{operation}' for node: #{node}" unless operations.has_key? operation
        plugin_name = operations[operation]
      end


      $logger.debug('Executing operation [operation={}, plugin={}]', operation, plugin_name)

      workitem.fields[TARGET] = CLOUDIFY_MANAGEMENT
      workitem.fields[PLUGIN_NAME] = "cosmo.#{plugin_name}.tasks"
      workitem.fields[WORKER_ID] = 'cloudify.management'
      if node[PLUGINS][plugin_name][AGENT_PLUGIN].to_s.eql? 'true'
        raise 'node does not contain a host_id property' unless node.has_key? HOST_ID
        workitem.fields[TARGET] = node[HOST_ID]
        workitem.fields[WORKER_ID] = "celery.#{node[HOST_ID]}"
      end
      # operation can have the interface name as its prefix: 'control.start' or just 'start'
      workitem.fields[OPERATION] = "cosmo.#{plugin_name}.tasks.#{operation.split('.')[-1]}"

      reply
    rescue Exception => e
      $logger.debug('Exception caught on prepare_operation participant execution: {}', e)
      raise e
    end
  end

end
