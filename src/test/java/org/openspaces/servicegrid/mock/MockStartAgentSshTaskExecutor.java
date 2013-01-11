package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;

public class MockStartAgentSshTaskExecutor {

	private TaskConsumerState state = new TaskConsumerState();

	public void execute(Task task, 
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartAgentTask) {
			AgentState impersonatedState = impersonatedStateModifier.getState();
			impersonatedState.setProgress(AgentState.Progress.AGENT_STARTED);
			impersonatedStateModifier.updateState(impersonatedState);
		}
		
	}

	public TaskConsumerState getState() {
		return state ;
	}

}
