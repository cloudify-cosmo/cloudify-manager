package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;

import com.google.common.base.Preconditions;

public class MockCloudMachineTaskExecutor {

	private final TaskExecutorState state = new TaskExecutorState();
	private TaskExecutorStateModifier impersonatedStateModifier;
	private final String ipAddressMock;
	
	public MockCloudMachineTaskExecutor() {
		ipAddressMock = null;
	}
	
	public MockCloudMachineTaskExecutor(String ipAddress) {
		this.ipAddressMock = ipAddress;
	}
	
	public void execute(Task task, TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartMachineTask) {
			this.impersonatedStateModifier = impersonatedStateModifier;
			AgentState agentState = impersonatedStateModifier.getState();
			Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.PLANNED));
			agentState.setProgress(AgentState.Progress.STARTING_MACHINE);
			impersonatedStateModifier.updateState(agentState);
		
			if(ipAddressMock != null) {
				signalLastStartedMachineFinished(ipAddressMock);
			}			
		}
	}
	
	public void signalLastStartedMachineFinished(String ipAddress){
		AgentState agentState = impersonatedStateModifier.getState();
		agentState.setProgress(AgentState.Progress.MACHINE_STARTED);
		agentState.setIpAddress(ipAddress);
		impersonatedStateModifier.updateState(agentState);
	}
	
	public TaskExecutorState getState() {
		return state;
	}
	
}
