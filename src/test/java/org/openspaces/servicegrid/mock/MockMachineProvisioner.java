package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.RestartNotRespondingAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;

import com.google.common.base.Preconditions;

public class MockMachineProvisioner {

	private final TaskConsumerState state = new TaskConsumerState();
	private final TaskConsumerRegistrar taskConsumerRegistrar;
	
	public MockMachineProvisioner(TaskConsumerRegistrar taskConsumerRegistrar) {
		this.taskConsumerRegistrar = taskConsumerRegistrar;
	}
	
	@ImpersonatingTaskConsumer
	public void startMachine(StartMachineTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
	
		//Simulate starting machine
		AgentState impersonatedState = impersonatedStateModifier.getState();
		Preconditions.checkState(impersonatedState.getProgress().equals(AgentState.Progress.PLANNED));
		impersonatedState.setProgress(AgentState.Progress.STARTING_MACHINE);
		impersonatedStateModifier.updateState(impersonatedState);
		//Immediately machine start 
		impersonatedStateModifier.getState();
		impersonatedState.setProgress(AgentState.Progress.MACHINE_STARTED);
		impersonatedStateModifier.updateState(impersonatedState);
	}


	@ImpersonatingTaskConsumer
	public void startAgent(StartAgentTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {

		AgentState agentState = impersonatedStateModifier.getState();
		Preconditions.checkNotNull(agentState);
		Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.MACHINE_STARTED));
		URI agentId = task.getImpersonatedTarget();
		Preconditions.checkState(agentId.toString().endsWith("/"));
		agentState.setProgress(AgentState.Progress.AGENT_STARTED);
		taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
		impersonatedStateModifier.updateState(agentState);
	}
	
	@ImpersonatingTaskConsumer
	public void restartAgent(RestartNotRespondingAgentTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
			
			//In a real implementation here is where we validate the agent process is killed
			AgentState agentState = impersonatedStateModifier.getState();
			Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.AGENT_STARTED));
			agentState.setNumberOfRestarts(agentState.getNumberOfRestarts() +1);
			URI agentId = task.getImpersonatedTarget();
			taskConsumerRegistrar.unregisterTaskConsumer(agentId);
			taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
			impersonatedStateModifier.updateState(agentState);
			//In a real implementation here is where we restart the agent process
	}

	@TaskConsumerStateHolder
	public TaskConsumerState getState() {
		return state;
	}

}
