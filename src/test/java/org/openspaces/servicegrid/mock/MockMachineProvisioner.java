package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
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
			TaskExecutorStateModifier<AgentState> impersonatedStateModifier) {
	
		//Simulate starting machine
		final AgentState impersonatedState = impersonatedStateModifier.getState(AgentState.class);
		Preconditions.checkState(impersonatedState.getProgress().equals(AgentState.Progress.PLANNED));
		impersonatedState.setProgress(AgentState.Progress.STARTING_MACHINE);
		impersonatedStateModifier.updateState(impersonatedState);
		//Immediately machine start 
		impersonatedStateModifier.getState(AgentState.class);
		impersonatedState.setProgress(AgentState.Progress.MACHINE_STARTED);
		impersonatedStateModifier.updateState(impersonatedState);
	}

	@ImpersonatingTaskConsumer
	public void terminateMachineOfNonResponsiveAgent(TerminateMachineOfNonResponsiveAgentTask task, TaskExecutorStateModifier<AgentState> impersonatedStateModifier) {
		final AgentState impersonatedState = impersonatedStateModifier.getState(AgentState.class);
		Preconditions.checkState(impersonatedState.getProgress().equals(AgentState.Progress.AGENT_STARTED));
		final URI agentId = task.getImpersonatedTarget();
		taskConsumerRegistrar.unregisterTaskConsumer(agentId);
		impersonatedState.setProgress(AgentState.Progress.MACHINE_TERMINATED);
		impersonatedStateModifier.updateState(impersonatedState);
	}
	
	@ImpersonatingTaskConsumer
	public void terminateMachine(TerminateMachineTask task, TaskExecutorStateModifier<AgentState> impersonatedStateModifier) {
		final AgentState agentState = impersonatedStateModifier.getState(AgentState.class);
		final String agentProgress = agentState.getProgress();
		Preconditions.checkState(
				agentProgress.equals(AgentState.Progress.STOPPING_AGENT) ||
				agentProgress.equals(AgentState.Progress.STARTING_MACHINE) ||
				agentProgress.equals(AgentState.Progress.MACHINE_STARTED) ||
				agentProgress.equals(AgentState.Progress.PLANNED));
		
		// code that makes sure the agent is no longer running and 
		// cannot change its own state comes here
		final URI agentId = task.getImpersonatedTarget();
		taskConsumerRegistrar.unregisterTaskConsumer(agentId);
			
		agentState.setProgress(AgentState.Progress.TERMINATING_MACHINE);
		impersonatedStateModifier.updateState(agentState);
		
		//actual code that terminates machine comes here
		
		agentState.setProgress(AgentState.Progress.MACHINE_TERMINATED);
		impersonatedStateModifier.updateState(agentState);

	}
	
	@ImpersonatingTaskConsumer
	public void startAgent(StartAgentTask task,
			TaskExecutorStateModifier<AgentState> impersonatedStateModifier) {

		final AgentState agentState = impersonatedStateModifier.getState(AgentState.class);
		Preconditions.checkNotNull(agentState);
		Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.MACHINE_STARTED));
		final URI agentId = task.getImpersonatedTarget();
		Preconditions.checkState(agentId.toString().endsWith("/"));
		agentState.setProgress(AgentState.Progress.AGENT_STARTED);
		taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
		impersonatedStateModifier.updateState(agentState);
	}

	@TaskConsumerStateHolder
	public TaskConsumerState getState() {
		return state;
	}

}
