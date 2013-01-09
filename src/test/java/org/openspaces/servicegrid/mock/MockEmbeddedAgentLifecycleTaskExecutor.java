package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.AgentTaskExecutor;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.DiagnoseAgentNotRespondingTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;

import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

public class MockEmbeddedAgentLifecycleTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	
	private final Map<URI, MockEmbeddedAgent> agents = Maps.newHashMap();
	private final TaskExecutorWrapper executorWrapper;

	public MockEmbeddedAgentLifecycleTaskExecutor(
			TaskExecutorWrapper executorWrapper) {
		this.executorWrapper = executorWrapper;
	}

	@Override
	public void execute(Task task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartAgentTask) {

			AgentState agentState = impersonatedStateModifier.getState();
			Preconditions.checkNotNull(agentState);
			URI agentExecutorId = ((StartAgentTask) task).getAgentExecutorId();
			Preconditions.checkState(agentExecutorId.toString().endsWith("/"));
			MockEmbeddedAgent agent = new MockEmbeddedAgent();
			agents.put(agentExecutorId, agent);
			agentState.setProgress(AgentState.Progress.AGENT_STARTED);
			executorWrapper.wrapTaskExecutor(new AgentTaskExecutor(agentState, agent), agentExecutorId);
			impersonatedStateModifier.updateState(agentState);
		}
		else if (task instanceof DiagnoseAgentNotRespondingTask) {

			AgentState agentState = impersonatedStateModifier.getState();
			agentState.setProgress(AgentState.Progress.AGENT_NOT_RESPONDING);
			impersonatedStateModifier.updateState(agentState);
		}
		else {
			Preconditions.checkState(false, "Cannot run task " + task.getClass());
		}

	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}

}
