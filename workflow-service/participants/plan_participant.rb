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
require_relative 'prepare_operation_participant'
require_relative 'plan_holder'

class PlanParticipant < Ruote::Participant

  def on_workitem
    begin

      unless workitem.fields.has_key? EXECUTION_ID
        raise 'execution_id field not set'
      end

      execution_id = workitem.fields[EXECUTION_ID]
      do_what = workitem.params['do']

      if do_what == 'modify_and_save_plan'
        unless workitem.fields.has_key? PrepareOperationParticipant::PLAN
          raise "#{PrepareOperationParticipant::PLAN} field not set"
        end
        plan = workitem.fields[PrepareOperationParticipant::PLAN]
        nodes_map = {}
        plan[PrepareOperationParticipant::NODES].each do |node|
          full_node = node.clone
          node['workflows'] = nil
          node['relationships'] = nil
          node['dependents'] = nil
          node['operations'] = nil
          node['plugins'] = nil
          nodes_map[node['id']] = full_node
        end
        plan[NODES_MAP] = nodes_map
        PlanHolder.put(execution_id, plan)
      elsif do_what == 'put_plan_on_workitem'
        plan = PlanHolder.get(execution_id)
        workitem.fields[PrepareOperationParticipant::PLAN] = plan
      elsif do_what == 'get_node_workflow'
        node_id = get_node_id(do_what)
        to_f = get_to_f(do_what)
        raise 'workflow_id not set' unless workitem.params.has_key? 'workflow_id'
        plan = PlanHolder.get(execution_id)
        workflow_id = workitem.params['workflow_id']
        to_f = workitem.params['to_f']
        workitem.fields[to_f] = plan[NODES_MAP][node_id]['workflows'][workflow_id]
      elsif do_what == 'get_node_relationships'
        node_id = get_node_id(do_what)
        to_f = get_to_f(do_what)
        plan = PlanHolder.get(execution_id)
        workitem.fields[to_f] = plan[NODES_MAP][node_id]['relationships']
      elsif do_what == 'get_node_dependents'
        node_id = get_node_id(do_what)
        to_f = get_to_f(do_what)
        plan = PlanHolder.get(execution_id)
        workitem.fields[to_f] = plan[NODES_MAP][node_id]['dependents']
      end
      reply
    rescue => e
      log_exception(workitem, e, 'plan_participant')
      flunk(workitem, e)
    end
  end

  def get_node_id(action)
    if workitem.fields.has_key? PrepareOperationParticipant::NODE
      return workitem.fields[PrepareOperationParticipant::NODE]['id']
    elsif workitem.params.has_key? 'node_id'
      return workitem.params['node_id']
    end
    raise "node_id was not set for action: #{action}"
  end

  def get_to_f(action)
    raise "to_f was not set for action: #{action}" unless workitem.params.has_key? 'to_f'
    return workitem.params['to_f']
  end

  def do_not_thread
    true
  end

end

