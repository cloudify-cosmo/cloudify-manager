package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

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
			ServiceInstanceState impersonatedState = impersonatedStateModifier.getState();
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
