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


class RuoteWorkflowEngine

  def initialize(opts = { :testing => false })
    @dashboard = Ruote::Dashboard.new(Ruote::Worker.new(Ruote::HashStorage.new))
    @dashboard.register_participant 'state', StateCacheParticipant
    @dashboard.register_participant 'execute_task', ExecuteTaskParticipant
    @dashboard.register_participant 'prepare_plan', PreparePlanParticipant
    @dashboard.register_participant 'prepare_operation', PrepareOperationParticipant
    @dashboard.register_participant 'log', LoggerParticipant
    @dashboard.register_participant 'event', EventParticipant
    @dashboard.register_participant 'collect_params', CollectParamsParticipant
    # in tests this will not work since Riemann is supposed to be running.
    testing = opts[:testing]
    unless testing
      @context = create_service_dependencies
      $ruote_properties = {
        'executor' => @context.get_bean('taskExecutor'),
        'state_cache' => @context.get_bean('stateCache')
      }
    end
    $logger = LoggerFactory.get_logger(RuoteRuntime.java_class)
    $user_logger = LoggerFactory.get_logger('cosmo')
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

  def launch(radial, fields={})
    workflow = Ruote::RadialReader.read(radial)
    wfid = @dashboard.launch(workflow, fields)
    WorkflowState.new(wfid, :pending, DateTime.now)
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
    #state = @dashboard.process(wfid)
    #if state
    #  puts "-- state is: #{state}"
    #  puts "-- state type is #{state.class}"
    #  puts "-- launched_time: #{state.launched_time}"
    #else
    #  puts "no state"
    #end
    #WorkflowState.new(wfid, :unknown, DateTime.now)
    raise 'not implemented'
  end

  def get_workflows
    raise 'not implemented'
  end

  def on_msg(context)
    raise 'not implemented'
  end

  private

  def load_built_in_workflows
    pattern = File.join(File.dirname(__FILE__), 'workflows/*.radial')
    Dir.glob(pattern).each do |file|
      radial = File.open(file).read
      wf_name = Pathname.new(file).basename.to_s.sub('.radial', '')
      @dashboard.variables[wf_name] = Ruote::RadialReader.read(radial)
    end
  end

end

