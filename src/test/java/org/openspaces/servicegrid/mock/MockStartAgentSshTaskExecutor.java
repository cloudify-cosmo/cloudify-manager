package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;

public class MockStartAgentSshTaskExecutor implements ImpersonatingTaskExecutor<TaskExecutorState> {

	private TaskExecutorState state = new TaskExecutorState();

	@Override
	public void execute(Task task, 
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartAgentTask) {
			AgentState impersonatedState = impersonatedStateModifier.getState();
			impersonatedState.setProgress(AgentState.Progress.AGENT_STARTED);
			impersonatedStateModifier.updateState(impersonatedState);
		}
		
	}

	@Override
	public TaskExecutorState getState() {
		return state ;
	}

}
