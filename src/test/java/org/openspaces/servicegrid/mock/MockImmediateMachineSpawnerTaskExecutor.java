package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class MockImmediateMachineSpawnerTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	
	@Override
	public void execute(Task task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartMachineTask) {
			//Simulate starting machine
			ServiceInstanceState impersonatedState = impersonatedStateModifier.getState();
			impersonatedState.setProgress(ServiceInstanceState.Progress.STARTING_MACHINE);
			impersonatedStateModifier.updateState(impersonatedState);
			//Immediately machine start 
			impersonatedStateModifier.getState();
			impersonatedState.setProgress(ServiceInstanceState.Progress.MACHINE_STARTED);
			impersonatedStateModifier.updateState(impersonatedState);
		}
	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}

}
