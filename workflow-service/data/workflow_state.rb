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

class WorkflowState

  attr_accessor :id, :state, :created, :launched, :error, :tags

  def initialize(id, state, created, tags, launched=nil, rev=nil)
    @id = id
    @state = state
    @created = created
    @tags = tags
    @launched = launched
    @error = nil
    @rev = rev
  end

  def to_json(*a)
    to_h(*a).to_json
  end

  def to_h(*a)
    result = {
        :id => @id,
        :state => @state,
        :created => @created,
        :launched => @launched,
        :error => @error,
        :tags => @tags,
    }
    unless @rev.nil?
      result['_rev'] = @rev
    end
    result
  end

  def self.from_hash(h)
    result = WorkflowState.new(
        h['id'],
        h['state'].to_sym,
        h['created'],
        h['tags'],
        h['launched'],
        h['_rev']
    )
    result.error = h['error']
    result
  end

end
