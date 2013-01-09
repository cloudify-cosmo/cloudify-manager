package org.openspaces.servicegrid.mock;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class MockStartAgentSshTaskExecutor implements ImpersonatingTaskExecutor<TaskExecutorState> {

	private TaskExecutorState state = new TaskExecutorState();

	@Override
	public void execute(Task task, 
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof StartAgentTask) {
			ServiceInstanceState impersonatedState = impersonatedStateModifier.getState();
			impersonatedState.setProgress(ServiceInstanceState.Progress.AGENT_STARTED);
			impersonatedState.setAgentExecutorId(((StartAgentTask) task).getAgentExecutorId());
			impersonatedStateModifier.updateState(impersonatedState);
		}
		
	}

	@Override
	public TaskExecutorState getState() {
		return state ;
	}

}
