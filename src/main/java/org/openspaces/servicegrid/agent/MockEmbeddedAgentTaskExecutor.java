package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;

public class MockEmbeddedAgentTaskExecutor {

	private final AgentState state;

	public MockEmbeddedAgentTaskExecutor(AgentState state) {
		this.state = state;
	}

	@TaskExecutor
	public void startServiceInstance(StartServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
		impersonatedStateModifier.updateState(instanceState);

	}

	@TaskExecutor
	public void installServiceInstance(InstallServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
		impersonatedStateModifier.updateState(instanceState);
	}

	@TaskExecutor
	public void execute(PingAgentTask task) {
		//do nothing
	}
	
	public TaskExecutorState getState() {
		return state;
	}


}
