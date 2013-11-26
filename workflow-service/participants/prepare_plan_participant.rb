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

require 'json'
require_relative 'exception_logger'

class PreparePlanParticipant < Ruote::Participant

  PLAN = 'plan'
  NODE = 'node'
  RUNTIME = 'cloudify_runtime'
  PROPERTIES = 'properties'

  def on_workitem
    begin
      raise 'plan not set' unless workitem.params.has_key? PLAN

      plan = workitem.params[PLAN]
      nodes = plan['nodes']

      nodes.each do |node|
        if node.has_key? 'relationships'
          node['relationships'].each do |relationship|
            relationship['workflow'] = Ruote::RadialReader.read(relationship['workflow'])
          end
        end
        workflows = Hash.new
        if node.has_key? 'workflows'
          node['workflows'].each { |key, value| workflows[key] = Ruote::RadialReader.read(value) }
        end
        node['workflows'] = workflows
      end

      if plan.has_key? 'workflows'
        workflows = Hash.new
        plan['workflows'].each do |key, value|
          workflows[key] = Ruote::RadialReader.read(value)
        end
        plan['workflows'] = workflows
      end

      workitem.fields['plan'] = plan

      $logger.debug('Prepared plan: {}', JSON.pretty_generate(plan))
      reply

    rescue => e
      log_exception(e, 'prepare_plan')
      flunk(workitem, e)
    end
  end
end