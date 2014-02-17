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

require 'singleton'

NODES_MAP = 'nodes_map'
EXECUTION_ID = 'execution_id'

class PlanHolder

  include Singleton

  def initialize
    # map from execution_id => plan
    @plans = {}
  end

  def plans
    @plans
  end

  def self.put(execution_id, plan)
    PlanHolder.instance.plans[execution_id] = plan
  end

  def self.get(execution_id)
    PlanHolder.instance.plans[execution_id]
  end

  def self.get_node(execution_id, node_id)
    PlanHolder.instance.plans[execution_id][NODES_MAP][node_id]
  end

end
