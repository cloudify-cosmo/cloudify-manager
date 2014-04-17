#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

require_relative 'states_holder'

class StatesHolder

  def initialize(storage)
    @storage = storage
  end

  def put(wfid, state)
    @storage.put({
      'type' => 'states',
      '_id' => wfid
    }.merge(state.to_h))
  end

  def []=(wfid, state)
    put(wfid, state)
  end

  def [](wfid)
    get(wfid)
  end

  def get(wfid)
    h = @storage.get('states', wfid)
    if h.nil?
      return nil
    end
    WorkflowState.from_hash(h)
  end

  def values
    @storage.get_many('states').map { |state| WorkflowState.from_hash(state) }
  end

  def has_key?(wfid)
    not @storage.get('states', wfid).nil?
  end

end
