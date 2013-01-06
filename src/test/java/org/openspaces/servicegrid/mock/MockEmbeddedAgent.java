package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.Agent;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.StartServiceInstanceTask;

public class MockEmbeddedAgent extends
		Agent {

	/* (non-Javadoc)
	 * @see org.openspaces.servicegrid.mock.Agent#startServiceInstance(org.openspaces.servicegrid.TaskExecutorStateModifier)
	 */
	@Override
	public void startServiceInstance(
			StartServiceInstanceTask task, TaskExecutorStateModifier impersonatedStateModifier) {
		super.startServiceInstance(task, impersonatedStateModifier);
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
		impersonatedStateModifier.updateState(instanceState);
	}

	/* (non-Javadoc)
	 * @see org.openspaces.servicegrid.mock.Agent#installServiceInstance(org.openspaces.servicegrid.TaskExecutorStateModifier)
	 */
	@Override
	public void installServiceInstance(
			InstallServiceInstanceTask task, TaskExecutorStateModifier impersonatedStateModifier) {
		super.installServiceInstance(task, impersonatedStateModifier);
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
		impersonatedStateModifier.updateState(instanceState);
	}

}
