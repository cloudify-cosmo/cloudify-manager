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

require 'java'
require 'ruote'
require 'json'
require 'thread'
require 'pathname'

require_relative '../../orchestrator/target/cosmo.jar'
require_relative '../participants/all'
require_relative '../data/workflow_state'

java_import org.cloudifysource.cosmo.statecache.StateCache
java_import org.cloudifysource.cosmo.tasks.EventHandler
java_import org.springframework.context.annotation.AnnotationConfigApplicationContext
java_import org.cloudifysource.cosmo.orchestrator.workflow.config.RuoteServiceDependenciesConfig
java_import org.cloudifysource.cosmo.logging.LoggerFactory
java_import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime
java_import org.apache.log4j.Logger
java_import org.apache.log4j.Level
java_import org.cloudifysource.cosmo.logger.CosmoBlueprintsFileAppender


class RuoteWorkflowEngine

  def initialize(opts={})
    @mutex = Mutex.new
    @states = Hash.new
    @dashboard = Ruote::Dashboard.new(Ruote::Worker.new(Ruote::HashStorage.new))
    @dashboard.register_participant 'state', StateCacheParticipant
    @dashboard.register_participant 'execute_task', ExecuteTaskParticipant
    @dashboard.register_participant 'prepare_plan', PreparePlanParticipant
    @dashboard.register_participant 'prepare_operation', PrepareOperationParticipant
    @dashboard.register_participant 'log', LoggerParticipant
    @dashboard.register_participant 'event', EventParticipant
    @dashboard.register_participant 'collect_params', CollectParamsParticipant
    @dashboard.add_service('ruote_listener', self)

    # in tests this will not work since Riemann is supposed to be running.
    test = opts[:test]
    if test.nil? or test.eql?(false)
      @context = create_service_dependencies
      $ruote_properties = {
        'executor' => @context.get_bean('taskExecutor'),
        'state_cache' => @context.get_bean('stateCache')
      }
    end

    # create loggers
    $logger = LoggerFactory.get_logger(RuoteRuntime.java_class)
    $user_logger = LoggerFactory.get_logger('cosmo')

    # setup events logs appender and path
    if ENV.has_key? 'WF_SERVICE_LOGS_PATH'
      user_logger = Logger.get_logger('cosmo')
      appender = CosmoBlueprintsFileAppender.new
      appender.set_path ENV['WF_SERVICE_LOGS_PATH']
      appender.set_name 'app'
      appender.set_threshold Level::DEBUG
      user_logger.add_appender appender
    end

    # load built in workflows
    load_built_in_workflows
  end

  def close
    @dashboard.shutdown
    if @context
      @context.close
    end
  end

  def create_service_dependencies
    context = AnnotationConfigApplicationContext.new
    context.register RuoteServiceDependenciesConfig.java_class
    context.refresh
    context
  end

  def launch(radial, fields={}, tags={})
    workflow = Ruote::RadialReader.read(radial)
    wfid = @dashboard.launch(workflow, fields)
    wf_state = update_workflow_state(wfid, :pending, tags)
    log_workflow_state(wf_state)
    wf_state
  end

  def cancel_workflow(wfid)
    raise 'not implemented'
  end

  def pause_workflow(wfid)
    raise 'not implemented'
  end

  # Ruote only keeps state for running workflows, that means that workflows which were just launched
  # but not yet started and terminated workflows won't have states kept in Ruote.
  def get_workflow_state(wfid)
    begin
      @mutex.lock
      verify_workflow_exists(wfid)

      return @states[wfid]
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

  def on_msg(context)
    new_state = nil
    error = nil

    # If wfid is not present in context it means this is a sub-workflow message
    # we don't handle such messages at this point - perhaps later when we want to
    # visualize workflow progress etc.. this might be relevant.
    unless context.has_key?('wfid')
      return
    end

    case context['action']
      when 'launch'
        new_state = :launched
      when 'terminated'
        new_state = :terminated
      when 'error_intercepted'
        new_state = :failed
        error = context['error']
      else
        # ignore..
    end
    unless new_state.nil?
      wf_state = update_workflow_state(context['wfid'], new_state, nil, error)
      log_workflow_state(wf_state)
    end
  end

  private

  def log_workflow_state(wf_state)
    event = wf_state.tags.clone
    event[:workflow_id] = wf_state.id
    event[:type] = wf_state.state
    event[:error] = wf_state.error unless wf_state.state != :failed
    $user_logger.debug("Workflow state changed #{JSON.pretty_generate(event)}")
  end

  def update_workflow_state(wfid, state, tags=nil, error=nil)
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
