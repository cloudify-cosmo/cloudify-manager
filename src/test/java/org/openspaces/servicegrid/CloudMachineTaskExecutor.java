package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class CloudMachineTaskExecutor implements ImpersonatingTaskExecutor<TaskExecutorState,ServiceInstanceState> {

	private final ServiceInstanceState impersonatedState = new ServiceInstanceState();
	private final ServiceInstanceState state = new ServiceInstanceState();
	
	@Override
	public void execute(Task task) {
		if (task instanceof StartMachineTask) {
			impersonatedState.setProgress(ServiceInstanceState.Progress.STARTING_MACHINE);
		}
		
	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}
	
	@Override
	public ServiceInstanceState getImpersonatedState() {
		return impersonatedState;
	}
	
}
