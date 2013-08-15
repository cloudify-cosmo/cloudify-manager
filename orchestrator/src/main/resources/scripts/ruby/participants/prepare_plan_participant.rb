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

java_import org.cloudifysource.cosmo.dsl.DSLProcessor
java_import org.cloudifysource.cosmo.dsl.PluginArtifactAwareDSLPostProcessor
require 'json'

class PreparePlanParticipant < Ruote::Participant

  DSL = 'dsl'
  HOST_TYPE = 'cloudify.tosca.types.host'
  PLUGIN_INSTALLER_PLUGIN = 'cloudify.tosca.artifacts.plugin.plugin_installer.installer'
  NODE = 'node'
  RUNTIME = 'cloudify_runtime'
  PROPERTIES = 'properties'

  def on_workitem
    begin
      raise 'dsl not set' unless workitem.params.has_key? 'dsl'

      dsl_file = workitem.params['dsl']

      processed_dsl = DSLProcessor.process(dsl_file, PluginArtifactAwareDSLPostProcessor.new)

      plan = JSON.parse(processed_dsl)
      nodes = plan['nodes']
      nodes_extra = plan['nodes_extra']
      nodes.each {|node| process_node(nodes_extra, node) }
      hosts_with_plugins = []
      nodes.each do |node|
        if nodes_extra[node['id']]['super_types'].include? HOST_TYPE
          add_plugins_to_install(node, nodes)
          if node[PROPERTIES]['install_agent'] == 'true'
            hosts_with_plugins << node['id']
          end
        end
        node[PROPERTIES][RUNTIME] = Hash.new
        execution_params_names = []
        node['relationships'].each do |relationship|
          relationship['state'] = 'reachable'
          relationship_workflow = plan['relationships'][relationship['type']]['workflow']
          if relationship_workflow.nil? or relationship_workflow.empty?
            relationship_workflow = 'define stub_workflow\n\t'
          end
          relationship['workflow'] = Ruote::RadialReader.read(relationship_workflow)
          relationship['execution_list'].each do |executed_item|
            output_field = executed_item['output_field']
            execution_params_names << output_field unless output_field.empty?
          end
          relationship['late_execution_list'].each do |executed_item|
            output_field = executed_item['output_field']
            execution_params_names << output_field unless output_field.empty?
          end
        end
        node['execution_params_names'] = execution_params_names
      end

      workitem.fields['plan'] = plan

      if plan.has_key? 'global_workflow'
        workitem.fields['global_workflow'] = Ruote::RadialReader.read(plan['global_workflow'])
      end

      $logger.debug('Prepared plan: {}', JSON.pretty_generate(plan))

      reply

    rescue Exception => e
      $logger.debug('Exception caught on prepare_plan participant execution: {}', e)
      raise e
    end
  end

  def process_node(nodes_extra, node)

    # parse workflows
    workflows = Hash.new
    node['workflows'].each { |key, value| workflows[key] = Ruote::RadialReader.read(value)  }
    node['workflows'] = workflows

    # extract host node id
    host_id = extract_host_id(nodes_extra, node['id'])
    node['host_id'] = host_id unless host_id.nil?

  end

  def extract_host_id(nodes_extra, node_id)
    current_node_extra = nodes_extra[node_id]
    if current_node_extra['super_types'].include? HOST_TYPE
      node_id
    else
      current_node_extra['relationships'].each do |relationship|
        relationship_host_id = extract_host_id(nodes_extra, relationship)
        return relationship_host_id unless relationship_host_id.nil?
      end
      nil
    end

  end

  def add_plugins_to_install(host_node, nodes)
    plugins_to_install = Hash.new
    nodes.each do |node|
      if node['host_id'] == host_node['id']
        # ok to override here since we assume it is the same plugin
        node['plugins'].each do |name, plugin|
          if plugin['agent_plugin'] == 'true' and plugin['name'] != PLUGIN_INSTALLER_PLUGIN
            plugins_to_install[name] = plugin
          end
        end
      end
    end
    host_node['plugins_to_install'] = plugins_to_install.values
  end

end
