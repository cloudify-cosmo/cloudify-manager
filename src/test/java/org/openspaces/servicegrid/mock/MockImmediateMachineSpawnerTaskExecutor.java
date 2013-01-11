package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;

public class MockImmediateMachineSpawnerTaskExecutor {

	private final TaskExecutorState state = new TaskExecutorState();
	
	@TaskExecutor
	public void startMachine(StartMachineTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
	
		//Simulate starting machine
		AgentState impersonatedState = impersonatedStateModifier.getState();
		impersonatedState.setProgress(AgentState.Progress.STARTING_MACHINE);
		impersonatedStateModifier.updateState(impersonatedState);
		//Immediately machine start 
		impersonatedStateModifier.getState();
		impersonatedState.setProgress(AgentState.Progress.MACHINE_STARTED);
		impersonatedStateModifier.updateState(impersonatedState);
	}

	public TaskExecutorState getState() {
		return state;
	}

}
