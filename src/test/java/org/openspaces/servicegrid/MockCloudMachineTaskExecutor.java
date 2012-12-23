package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class MockCloudMachineTaskExecutor implements ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	private TaskExecutorStateModifier impersonatedStateModifier;
	
	@Override
	public void execute(Task task, TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartMachineTask) {
			this.impersonatedStateModifier = impersonatedStateModifier;
				final ServiceInstanceState impersonatedState = new ServiceInstanceState();
				impersonatedState.setProgress(ServiceInstanceState.Progress.STARTING_MACHINE);
				impersonatedStateModifier.updateState(impersonatedState);
		}
	}
	
	public void signalLastStartedMachineFinished(String ipAddress){
		ServiceInstanceState impersonatedState = new ServiceInstanceState();
		impersonatedState.setProgress(ServiceInstanceState.Progress.MACHINE_STARTED);
		impersonatedState.setIpAddress(ipAddress);
		impersonatedStateModifier.updateState(impersonatedState);
	}
	
	@Override
	public TaskExecutorState getState() {
		return state;
	}
	
}
