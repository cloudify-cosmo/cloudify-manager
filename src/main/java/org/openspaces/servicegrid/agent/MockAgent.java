package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;

public class MockAgent {

	private final AgentState state;

	public MockAgent(AgentState state) {
		this.state = state;
	}

	@ImpersonatingTaskConsumer
	public void startServiceInstance(StartServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
		impersonatedStateModifier.updateState(instanceState);

	}

	@ImpersonatingTaskConsumer
	public void installServiceInstance(InstallServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
		impersonatedStateModifier.updateState(instanceState);
	}

	@TaskConsumer
	public void execute(PingAgentTask task) {
		//do nothing
	}
	
	public TaskConsumerState getState() {
		return state;
	}


}
