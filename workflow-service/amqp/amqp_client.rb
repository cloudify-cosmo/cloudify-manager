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
    settings = {
      :auto_delete => true,
      :durable => true,
      :exclusive => false
    }
    @conn = MarchHare.connect
    @channel = @conn.create_channel
    @events_queue = @channel.queue('cloudify-events', settings)
    @logs_queue = @channel.queue('cloudify-logs', settings)
  end

  def self.publish_event(type, event={})
    AMQPClient.instance.publish_event(type, event)
  end

  def self.publish_log(level, message, context={})
    AMQPClient.instance.publish_log(level, message, context)
  end

  def publish_event(type, context={})
    raise 'Cannot create amqp message - workitem not in message_params' unless context.has_key? :workitem
    context[:message] = {
        :text => context[:message] || nil,
        :arguments => context[:arguments] || nil
    }
    event = generate_amqp_message(context)
    event[:type] = :cloudify_event
    event[:event_type] = type
    @events_queue.publish(event.to_json,
                          :routing_key => 'logstash')
  end

  def publish_log(level, message, context)
    context[:message] = {
        :text => message,
        :arguments => context[:arguments] || nil
    }
    log = generate_amqp_message(context)
    log[:logger] = context[:logger] || :ruote
    log[:level] = level
    log[:type] = :cloudify_log
    @logs_queue.publish(log.to_json,
                        :routing_key => 'logstash')
  end

  def generate_amqp_message(message_params={})
    workitem = message_params[:workitem] || nil
    message = {
      :code => message_params[:code] || nil,
      :timestamp => Time.now.to_s,
      :message => message_params[:message] || nil,
      :context => {
        :operation => message_params[:operation] || nil,
        :plugin => message_params[:plugin] || nil,
        :task_name => message_params[:task_name] || nil,
        :task_id => message_params[:task_id] || nil,
        :task_target => message_params[:task_target] || nil,
      }
    }
    if not workitem.nil?
      if workitem.fields.has_key? 'node'
        message[:context][:node_id] = workitem.fields['node']['id']
        message[:context][:node_name] = workitem.fields['node']['name'] || nil
      end
      message[:context][:blueprint_id] = workitem.fields['blueprint_id'] || nil
      message[:context][:deployment_id] = workitem.fields['deployment_id'] || nil
      message[:context][:workflow_id] = workitem.fields['workflow_id'] || nil
      message[:context][:execution_id] = workitem.fields['execution_id'] || nil
      message[:context][:wfid] = workitem.wfid
    end
    return message
  end

end