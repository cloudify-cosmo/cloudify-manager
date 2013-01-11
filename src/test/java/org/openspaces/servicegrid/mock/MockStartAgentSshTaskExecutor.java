package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;

public class MockStartAgentSshTaskExecutor {

	private TaskExecutorState state = new TaskExecutorState();

	public void execute(Task task, 
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartAgentTask) {
			AgentState impersonatedState = impersonatedStateModifier.getState();
			impersonatedState.setProgress(AgentState.Progress.AGENT_STARTED);
			impersonatedStateModifier.updateState(impersonatedState);
		}
		
	}

	public TaskExecutorState getState() {
		return state ;
	}

}
