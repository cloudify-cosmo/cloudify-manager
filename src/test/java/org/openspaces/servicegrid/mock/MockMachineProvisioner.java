package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskConsumerStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;
import org.openspaces.servicegrid.agent.tasks.TerminateMachineOfNonResponsiveAgentTask;
import org.openspaces.servicegrid.agent.tasks.TerminateMachineTask;

import com.google.common.base.Preconditions;

public class MockMachineProvisioner {

	private final TaskConsumerState state = new TaskConsumerState();
	private final TaskConsumerRegistrar taskConsumerRegistrar;
	
	public MockMachineProvisioner(TaskConsumerRegistrar taskConsumerRegistrar) {
		this.taskConsumerRegistrar = taskConsumerRegistrar;
	}
	
	@ImpersonatingTaskConsumer
	public void startMachine(StartMachineTask task,
			TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {
	
		//Simulate starting machine
		final AgentState impersonatedState = impersonatedStateModifier.get();
		Preconditions.checkState(impersonatedState.getProgress().equals(AgentState.Progress.PLANNED));
		impersonatedState.setProgress(AgentState.Progress.STARTING_MACHINE);
		impersonatedStateModifier.put(impersonatedState);
		//Immediately machine start 

		impersonatedState.setProgress(AgentState.Progress.MACHINE_STARTED);
		impersonatedStateModifier.put(impersonatedState);
	}

	@ImpersonatingTaskConsumer
	public void terminateMachineOfNonResponsiveAgent(TerminateMachineOfNonResponsiveAgentTask task, TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {
		final AgentState impersonatedState = impersonatedStateModifier.get();
		Preconditions.checkState(impersonatedState.getProgress().equals(AgentState.Progress.AGENT_STARTED));
		final URI agentId = task.getStateId();
		taskConsumerRegistrar.unregisterTaskConsumer(agentId);
		impersonatedState.setProgress(AgentState.Progress.MACHINE_TERMINATED);
		impersonatedStateModifier.put(impersonatedState);
	}
	
	@ImpersonatingTaskConsumer
	public void terminateMachine(TerminateMachineTask task, TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {
		final AgentState agentState = impersonatedStateModifier.get();
		final String agentProgress = agentState.getProgress();
		Preconditions.checkState(
				agentProgress.equals(AgentState.Progress.MACHINE_MARKED_FOR_TERMINATION) ||
				agentProgress.equals(AgentState.Progress.STARTING_MACHINE) ||
				agentProgress.equals(AgentState.Progress.MACHINE_STARTED) ||
				agentProgress.equals(AgentState.Progress.PLANNED));
		
		// code that makes sure the agent is no longer running and 
		// cannot change its own state comes here
		final URI agentId = task.getStateId();
		taskConsumerRegistrar.unregisterTaskConsumer(agentId);
			
		agentState.setProgress(AgentState.Progress.TERMINATING_MACHINE);
		impersonatedStateModifier.put(agentState);
		
		//actual code that terminates machine comes here
		
		agentState.setProgress(AgentState.Progress.MACHINE_TERMINATED);
		impersonatedStateModifier.put(agentState);

	}
	
	@ImpersonatingTaskConsumer
	public void startAgent(StartAgentTask task,
			TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {

		final AgentState agentState = impersonatedStateModifier.get();
		Preconditions.checkNotNull(agentState);
		Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.MACHINE_STARTED));
		final URI agentId = task.getStateId();
		Preconditions.checkState(agentId.toString().endsWith("/"));
		agentState.setProgress(AgentState.Progress.AGENT_STARTED);
		taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
		impersonatedStateModifier.put(agentState);
	}

	@TaskConsumerStateHolder
	public TaskConsumerState getState() {
		return state;
	}

}
