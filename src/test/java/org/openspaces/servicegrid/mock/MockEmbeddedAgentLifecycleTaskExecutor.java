package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.MockEmbeddedAgentTaskExecutor;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.RestartNotRespondingAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;

import com.google.common.base.Preconditions;

public class MockEmbeddedAgentLifecycleTaskExecutor {

	private final TaskExecutorState state = new TaskExecutorState();
	
	private final TaskExecutorWrapper executorWrapper;

	public MockEmbeddedAgentLifecycleTaskExecutor(
			TaskExecutorWrapper executorWrapper) {
		this.executorWrapper = executorWrapper;
	}

	@ImpersonatingTaskExecutor
	public void startAgent(StartAgentTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {

		AgentState agentState = impersonatedStateModifier.getState();
		Preconditions.checkNotNull(agentState);
		Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.MACHINE_STARTED));
		URI agentId = task.getImpersonatedTarget();
		Preconditions.checkState(agentId.toString().endsWith("/"));
		agentState.setProgress(AgentState.Progress.AGENT_STARTED);
		executorWrapper.wrapTaskExecutor(new MockEmbeddedAgentTaskExecutor(agentState), agentId);
		impersonatedStateModifier.updateState(agentState);
	}
	
	@ImpersonatingTaskExecutor
	public void restartAgent(RestartNotRespondingAgentTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
			
			//In a real implementation here is where we validate the agent process is killed
			AgentState agentState = impersonatedStateModifier.getState();
			Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.AGENT_STARTED));
			agentState.setNumberOfRestarts(agentState.getNumberOfRestarts() +1);
			URI agentId = task.getImpersonatedTarget();
			executorWrapper.removeTaskExecutor(agentId);
			executorWrapper.wrapTaskExecutor(new MockEmbeddedAgentTaskExecutor(agentState), agentId);
			impersonatedStateModifier.updateState(agentState);
			//In a real implementation here is where we restart the agent process
	}

	public TaskExecutorState getState() {
		return state;
	}

}
