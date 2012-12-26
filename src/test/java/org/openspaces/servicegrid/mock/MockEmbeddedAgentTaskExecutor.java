package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.StartServiceInstanceTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class MockEmbeddedAgentTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();

	@Override
	public void execute(Task task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof InstallServiceInstanceTask){
			ServiceInstanceState instanceState = impersonatedStateModifier.getState();
			instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
			impersonatedStateModifier.updateState(instanceState);
			instanceState = impersonatedStateModifier.getState();
			instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
			impersonatedStateModifier.updateState(instanceState);
		} else if (task instanceof StartServiceInstanceTask){
			ServiceInstanceState instanceState = impersonatedStateModifier.getState();
			instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
			impersonatedStateModifier.updateState(instanceState);
			instanceState = impersonatedStateModifier.getState();
			instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
			impersonatedStateModifier.updateState(instanceState);
		}
		
	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}

}
