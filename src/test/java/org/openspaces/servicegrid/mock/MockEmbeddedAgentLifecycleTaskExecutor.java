package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.AgentTaskExecutor;
import org.openspaces.servicegrid.agent.tasks.ResolveAgentNotRespondingTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

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

			ServiceInstanceState impersonatedState = impersonatedStateModifier.getState();
			
			URI agentExecutorId = ((StartAgentTask) task).getAgentExecutorId();
			Preconditions.checkState(agentExecutorId.toString().endsWith("/"));
			MockEmbeddedAgent agent = new MockEmbeddedAgent();
			agents.put(agentExecutorId, agent);
			executorWrapper.wrapTaskExecutor(new AgentTaskExecutor(agent), agentExecutorId);
			impersonatedState.setProgress(ServiceInstanceState.Progress.AGENT_STARTED);
			impersonatedState.setAgentExecutorId(agentExecutorId);
			impersonatedStateModifier.updateState(impersonatedState);
		}
		else if (task instanceof ResolveAgentNotRespondingTask) {

			ResolveAgentNotRespondingTask markAgentZombieTask = (ResolveAgentNotRespondingTask) task;
			ServiceInstanceState impersonatedState = impersonatedStateModifier.getState();
			Preconditions.checkArgument(impersonatedState.getAgentExecutorId().equals(markAgentZombieTask.getZombieAgentExecutorId()));
			impersonatedState.setProgress(ServiceInstanceState.Progress.AGENT_NOT_RESPONDING);
			impersonatedStateModifier.updateState(impersonatedState);
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
