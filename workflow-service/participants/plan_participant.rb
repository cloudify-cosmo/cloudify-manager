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
          nodes_map[node[PrepareOperationParticipant::NODE_ID]] = node
        end
        plan[NODES_MAP] = nodes_map
        PlanHolder.put(execution_id, plan)
      elsif do_what == 'put_plan_on_workitem'
        plan = PlanHolder.get(execution_id)
        workitem.fields[PrepareOperationParticipant::PLAN] = plan
      end
      reply
    rescue => e
      log_exception(workitem, e, 'plan_participant')
      flunk(workitem, e)
    end
  end

  def do_not_thread
    true
  end

end

