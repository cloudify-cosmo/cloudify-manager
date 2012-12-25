package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class MockCloudMachineTaskExecutor implements ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	private TaskExecutorStateModifier impersonatedStateModifier;
	private final String ipAddressMock;
	
	public MockCloudMachineTaskExecutor() {
		ipAddressMock = null;
	}
	
	public MockCloudMachineTaskExecutor(String ipAddress) {
		this.ipAddressMock = ipAddress;
	}
	
	@Override
	public void execute(Task task, TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartMachineTask) {
			this.impersonatedStateModifier = impersonatedStateModifier;
			ServiceInstanceState impersonatedState = new ServiceInstanceState();
			impersonatedState.setProgress(ServiceInstanceState.Progress.STARTING_MACHINE);
			impersonatedStateModifier.updateState(impersonatedState);
		
			if(ipAddressMock != null) {
				signalLastStartedMachineFinished(ipAddressMock);
			}			
		}
	}
	
	public void signalLastStartedMachineFinished(String ipAddress){
		ServiceInstanceState impersonatedState = impersonatedStateModifier.getState();
		impersonatedState.setProgress(ServiceInstanceState.Progress.MACHINE_STARTED);
		impersonatedState.setIpAddress(ipAddress);
		impersonatedStateModifier.updateState(impersonatedState);
	}
	
	@Override
	public TaskExecutorState getState() {
		return state;
	}
	
}
