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

require 'ruote'
require 'ruote-fs'
require 'json'
require 'thread'
require 'pathname'
require 'rest_client'

require_relative '../participants/all'
require_relative '../participants/plan_holder'
require_relative '../data/workflow_state'
require_relative '../utils/logs'
require_relative '../utils/events'
require_relative '../amqp/task_executor'

class RuoteWorkflowEngine

  def initialize(opts={})
    test = opts[:test]
    test = !test.nil? && test.eql?(true)

    if test
      storage = Ruote::HashStorage.new
    else
      storage_path = ENV['RUOTE_STORAGE_DIR_PATH']
      storage = Ruote::FsStorage.new(storage_path)
    end

    @mutex = Mutex.new
    @states = {}

    @dashboard = Ruote::Dashboard.new(Ruote::Worker.new(storage))
    @dashboard.add_service('ruote_listener', self)
    @dashboard.register_participant 'wait_for_node_state', NodeStateParticipant
    @dashboard.register_participant 'execute_task', ExecuteTaskParticipant
    @dashboard.register_participant 'prepare_plan', PreparePlanParticipant
    @dashboard.register_participant 'prepare_operation', PrepareOperationParticipant
    @dashboard.register_participant 'log', LoggerParticipant
    @dashboard.register_participant 'event', EventParticipant
    @dashboard.register_participant 'collect_params', CollectParamsParticipant
    @dashboard.register_participant 'plan_helper', PlanParticipant

    # in tests this will not work since Riemann is supposed to be running.
    unless test
      $ruote_properties = {
        'executor' => TaskExecutor.new,
      }
    end

    # create loggers
    $logger = StubLogger.new

    # load built in workflows
    load_built_in_workflows
  end

  def close
    @dashboard.shutdown
  end

  def launch(radial, fields={}, tags={})
    workflow = Ruote::RadialReader.read(radial)
    tags.each do |key, value|
      fields[key] = value unless fields.has_key? key
    end
    wfid = @dashboard.launch(workflow, fields)
    wf_state = update_workflow_state(nil, wfid, :pending, tags)
    log_workflow_state(wf_state)
    wf_state
  end

  def cancel_workflow(wfid)
    wf = get_workflow_state(wfid)
    @dashboard.cancel(wf.id)
    wf
  end

  def pause_workflow(wfid)
    raise 'not implemented'
  end

  def get_workflow_state(wfid)
    begin
      @mutex.lock
      verify_workflow_exists(wfid)
      return @states[wfid]
    ensure
      @mutex.unlock
    end
  end

  # Ruote only keeps state for running workflows, that means that workflows which were just launched
  # but not yet started and terminated workflows won't have states kept in Ruote.
  def get_workflows_states(workflows_ids)
    begin
      @mutex.lock
      result = []
      for wfid in workflows_ids do
        if @states.has_key?(wfid)
          result.push(@states[wfid])
        end
      end
      return result
    ensure
      @mutex.unlock
    end
  end

  def get_workflows
    begin
      @mutex.lock
      @states.values
    ensure
      @mutex.unlock
    end
  end

  def get_workflows_with_ruote_state
    {
        # duplicate workflows inner state as we are changing it
        :workflows => JSON.parse(get_workflows.to_json),
        :leftovers => @dashboard.leftovers,
        :processes => @dashboard.processes
    }
  end

  def on_msg(context)
    action = context['action']

    # handle error interception (both parent and sub workflows)
    begin
      if action == 'error_intercepted' and context.has_key?('fei') and not context['fei'].nil?
        wfid = context['fei']['wfid']
        wf_state = get_workflow_state(wfid)
        if wf_state.state != :failed
          @dashboard.cancel(wfid)
          new_state = :failed
          wf_state = update_workflow_state(context['workitem'], wfid,
                                           new_state, nil, context['error'])
          log_workflow_state(wf_state)
        end
      elsif action == 'cancel'
        flavour = context['flavour'] || nil
        if flavour == 'timeout'
          return
        end
        wfid = context['fei']['wfid']
        wf_state = get_workflow_state(wfid)
        if not [:cancelled, :failed].include? wf_state.state
          new_state = :cancelled
          wf_state = update_workflow_state(context['workitem'], wfid,
                                           new_state)
          log_workflow_state(wf_state)
        end
        return

      # Handle parent workflows (only parent as wfid on context)
      elsif context.has_key?('wfid') and context.has_key?('workitem')

        workitem = Ruote::Workitem.new(context['workitem'] || {})
        workflow_id = workitem.fields['workflow_id'] || nil

        new_state = nil

        if action == 'launch'
          send_event(:workflow_started, "Starting '#{workflow_id}' workflow execution", workitem)
          new_state = :launched
        elsif action == 'terminated'
          wf_state = get_workflow_state(workitem.wfid)
          if wf_state.state == :failed
            send_event(:workflow_failed, "'#{workflow_id}' workflow execution failed: #{wf_state.error}", workitem)
          elsif wf_state.state == :cancelled
            send_event(:workflow_cancelled, "'#{workflow_id}' workflow execution failed: #{wf_state.error}", workitem)
            new_state = :terminated
          else
            send_event(:workflow_succeeded, "'#{workflow_id}' workflow execution succeeded", workitem)
            new_state = :terminated
          end
          clear_plan_if_exists(workitem)
        end

        unless new_state.nil?
          wf_state = update_workflow_state(context['workitem'],
                                           context['wfid'], new_state)
          log_workflow_state(wf_state)
        end

      end
    rescue => exception
      log(:error, "Exception caught in route message handler: #{exception}: #{exception.backtrace}")
    end
  end

  private

  def clear_plan_if_exists(workitem)
    if workitem.fields.has_key?(EXECUTION_ID)
      begin
        PlanHolder.delete(workitem[EXECUTION_ID])
      rescue => exception
        log(:debug, "Exception caught in while trying to clear plan: #{exception}: #{exception.backtrace}")
      end
    end
  end

  def send_event(event_type, message, workitem, error=nil)
    event = {
        :workitem => workitem,
        :message => message
    }
    if not error.nil?
      event[:arguments] = {
          :error => error
      }
    end
    AMQPClient::publish_event(event_type, event)
  end

  def log_workflow_state(wf_state)
    event = wf_state.tags.clone
    event[:workflow_id] = wf_state.id
    case wf_state.state
      when :pending
        event[:type] = :workflow_received
      when :launched
        event[:type] = :workflow_started
      when :terminated
        event[:type] = :workflow_terminated
      when :failed
        event[:type] = :workflow_failed
        event[:error] = wf_state.error
    end
    log(:debug, "workflow state changed: #{event[:type]}", {
        :wfid => wf_state.id,
        :arguments => {
            :event => event
        }
    })
  end

  def update_workflow_state(workitem, wfid, state, tags=nil, error=nil)
    begin
      @mutex.lock
      if state.eql?(:pending)
        new_state = WorkflowState.new(wfid, state, DateTime.now, tags)
        @states[wfid] = new_state
        return new_state
      end
      wf_state = verify_workflow_exists(wfid)
      wf_state.state = state
      if state.eql?(:launched)
        wf_state.launched = DateTime.now
      elsif state.eql?(:failed)
        wf_state.error = error
      end

      # updating the storage wf state as well
      url = URI::escape("http://localhost:8100/executions/#{workitem["fields"][EXECUTION_ID]}")
      if state.eql?(:failed)
        body = JSON.generate({
                                 :status => wf_state.state,
                                 :error => error
                             })
      else
        body = JSON.generate({
                                 :status => wf_state.state
                             })
      end
      RestClient.patch url, body, {:content_type => :json}

      wf_state
    ensure
      @mutex.unlock
    end
  end

  def verify_workflow_exists(wfid)
    raise WorkflowDoesntExistError.new(wfid) unless @states.has_key?(wfid)
    @states[wfid]
  end

  def load_built_in_workflows
    pattern = File.join(File.dirname(__FILE__), '../workflows/*.radial')
    Dir.glob(pattern).each do |file|
      radial = File.open(file).read
      wf_name = Pathname.new(file).basename.to_s.sub('.radial', '')
      @dashboard.variables[wf_name] = Ruote::RadialReader.read(radial)
    end
  end

end

class WorkflowDoesntExistError < Exception
  def initialize(wfid)
    super("Workflow doesn't exist [wfid=#{wfid}]")
  end
end
