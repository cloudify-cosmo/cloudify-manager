package org.openspaces.servicegrid.mock;

import java.net.URL;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.AgentTaskExecutor;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Maps;

public class MockEmbeddedAgentLifecycleTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	
	private final Map<URL, MockEmbeddedAgent> agents = Maps.newHashMap();
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
			
			URL agentExecutorId = ((StartAgentTask) task).getAgentExecutorId();
			MockEmbeddedAgent agent = new MockEmbeddedAgent();
			agents.put(agentExecutorId, agent);
			executorWrapper.wrapImpersonatingTaskExecutor(new AgentTaskExecutor(agent), agentExecutorId);
			impersonatedState.setProgress(ServiceInstanceState.Progress.AGENT_STARTED);
			impersonatedState.setAgentExecutorId(agentExecutorId);
			impersonatedStateModifier.updateState(impersonatedState);
		}

	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}

}
