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

  HOST_TYPE = 'cloudify.tosca.types.host'

  def on_workitem
    begin
      raise 'dsl not set' unless workitem.params.has_key? 'dsl'

      dsl_file = workitem.params['dsl']

      processed_dsl = DSLProcessor.process(dsl_file, PluginArtifactAwareDSLPostProcessor.new)

      plan = JSON.parse(processed_dsl)
      plan['nodes'].each {|node| process_node(plan['nodes_extra'], node) }

      workitem.fields['plan'] = plan

      if plan.has_key? 'global_workflow'
        workitem.fields['global_workflow'] = Ruote::RadialReader.read(plan['global_workflow'])
      end

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

end
