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

require 'json'
require 'singleton'
require 'march_hare'

class AMQPClient
  include Singleton

  def initialize
    @conn = MarchHare.connect
    @channel = @conn.create_channel
    @queue = @channel.queue('cloudify-events')
  end

  def self.publish_event(event={})
    AMQPClient.instance.publish_event(event)
  end

  def publish_event(event={})
    workitem = event[:workitem]
    node_id = nil
    node_name = nil
    if workitem.fields.has_key? 'node'
      node_id = workitem.fields['node']['id']
      node_name = workitem.fields['node']['name'] || 'n/a'
    end
    event = {
        :bundle_code => event[:bundle_code] || nil,
        :timestamp => Time.now.to_s,
        :type => event[:type] || nil,
        :message => event[:message] || nil,
        :context => {
            :operation => event[:operation] || nil,
            :plugin => event[:plugin] || nil,
            :task_name => event[:task_name] || nil,
            :task_id => event[:task_id] || nil,
            :task_target => event[:task_target] || nil,
            :node_id => node_id,
            :node_name => node_name,
            :blueprint_id => workitem.fields['blueprint_id'] || 'n/a',
            :deployment_id => workitem.fields['deployment_id'] || 'n/a',
            :workflow_id => workitem.fields['workflow_id'] || 'n/a',
            :execution_id => workitem.fields['execution_id'] || 'n/a',
            :wfid => workitem.wfid
        }
    }
    @queue.publish(event.to_json, :routing_key => @queue.name)
  end


end