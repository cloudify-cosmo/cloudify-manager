package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.AgentTaskExecutor;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.RestartNotRespondingAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;

import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

public class MockEmbeddedAgentLifecycleTaskExecutor {

	private final TaskExecutorState state = new TaskExecutorState();
	
	private final Map<URI, MockEmbeddedAgent> agents = Maps.newHashMap();
	private final TaskExecutorWrapper executorWrapper;

	public MockEmbeddedAgentLifecycleTaskExecutor(
			TaskExecutorWrapper executorWrapper) {
		this.executorWrapper = executorWrapper;
	}

	public void execute(Task task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartAgentTask) {

			AgentState agentState = impersonatedStateModifier.getState();
			Preconditions.checkNotNull(agentState);
			Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.MACHINE_STARTED));
			URI agentId = ((StartAgentTask) task).getImpersonatedTarget();
			Preconditions.checkState(agentId.toString().endsWith("/"));
			MockEmbeddedAgent agent = new MockEmbeddedAgent();
			agents.put(agentId, agent);
			agentState.setProgress(AgentState.Progress.AGENT_STARTED);
			executorWrapper.wrapTaskExecutor(new AgentTaskExecutor(agentState, agent), agentId);
			impersonatedStateModifier.updateState(agentState);
		}
		else if (task instanceof RestartNotRespondingAgentTask) {
			
			//In a real implementation here is where we validate the agent process is killed
			AgentState agentState = impersonatedStateModifier.getState();
			Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.AGENT_STARTED));
			agentState.setNumberOfRestarts(agentState.getNumberOfRestarts() +1);
			URI agentId = task.getImpersonatedTarget();
			MockEmbeddedAgent agent = new MockEmbeddedAgent();
			executorWrapper.removeTaskExecutor(agentId);
			executorWrapper.wrapTaskExecutor(new AgentTaskExecutor(agentState, agent), agentId);
			impersonatedStateModifier.updateState(agentState);
			//In a real implementation here is where we restart the agent process
		}
		else {
			Preconditions.checkState(false, "Cannot run task " + task.getClass());
		}

	}

	public TaskExecutorState getState() {
		return state;
	}

}
