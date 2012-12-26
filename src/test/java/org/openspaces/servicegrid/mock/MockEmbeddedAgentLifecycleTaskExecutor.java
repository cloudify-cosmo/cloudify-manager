package org.openspaces.servicegrid.mock;

import java.net.URL;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Maps;

public class MockEmbeddedAgentLifecycleTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	
	private final Map<URL, MockEmbeddedAgentTaskExecutor> agents = Maps.newHashMap();
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
			MockEmbeddedAgentTaskExecutor agentTaskExecutor = new MockEmbeddedAgentTaskExecutor();
			agents.put(agentExecutorId, agentTaskExecutor);
			executorWrapper.wrapImpersonatingTaskExecutor(agentTaskExecutor, agentExecutorId);
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
