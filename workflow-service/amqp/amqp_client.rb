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
require 'bunny'

class AMQPClient
  include Singleton

  def initialize
    settings = {
      :auto_delete => true,
      :durable => true,
      :exclusive => false
    }
    @conn = Bunny.new.start
    @channel = @conn.create_channel
    @events_queue = @channel.queue('cloudify-events', settings)
    @logs_queue = @channel.queue('cloudify-logs', settings)

    initialize_celery_client!
  end

  def self.publish_event(type, event={})
    AMQPClient.instance.publish_event(type, event)
  end

  def self.publish_log(level, message, context={})
    AMQPClient.instance.publish_log(level, message, context)
  end

  def self.send_to_celery_queue(message, queue_name, handler)
    AMQPClient.instance.send_to_celery_queue(message, queue_name, handler)
  end

  def initialize_celery_client!
    @celery = {}
    @celery[:bound_queues] = {}
    @celery[:task_event_handlers] = {}
    @celery[:request_exchange] = @channel.direct('celery', :durable => true)
    @celery[:event_exchange] = @channel.topic('celeryev', :durable => true)
    @celery[:event_queue] = @channel.queue('celeryev', {
        :auto_delete => true,
        :durable => false,
        :exclusive => false
    })
    @celery[:event_queue].bind(@celery[:event_exchange], :routing_key => "#")
    # TODO it seems that messages could be received more than once
    # TODO check it out, this probably has something to do with the exchange
    #
    # TODO also need to handle handlers that are not cleaned due to
    # task ended event never arriving. Use some self cleanup mechanism
    # that is tied to the task timeout
    @celery[:event_queue].subscribe do |_, _, payload|
      payload = JSON.parse(payload)
      event_type = payload['type']
      if celery_task_event?(event_type)
        task_id = payload['uuid']
        handler = @celery[:task_event_handlers][task_id]
        unless handler.nil?
          handler.onTaskEvent(task_id, event_type, payload)
          if celery_task_ended_event?(event_type)
            @celery[:task_event_handlers].delete(task_id)
          end
        end
      end
    end
  end

  def celery_task_event?(event_type)
    event_type.respond_to?(:start_with?) && event_type.start_with?('task-')
  end

  def celery_task_ended_event?(event_type)
    event_type == 'task-succeeded' || event_type == 'task-failed' || event_type == 'task-revoked'
  end

  def send_to_celery_queue(message, queue_name, handler)
    @celery[:task_event_handlers][message[:id].to_s] = handler
    queue = @channel.queue(queue_name, {
        :auto_delete => false,
        :durable => true,
        :exclusive => false
    })
    # TODO this cache never gets cleaned. Make this cache clean once in a while
    unless @celery[:bound_queues].has_key?(queue_name)
      queue.bind(@celery[:request_exchange], :routing_key => queue_name)
      @celery[:bound_queues][queue_name] = @celery[:request_exchange]
    end
    queue.publish(message.to_json, {
        :content_type => 'application/json'
    })
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
      :message_code => message_params[:message_code] || nil,
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