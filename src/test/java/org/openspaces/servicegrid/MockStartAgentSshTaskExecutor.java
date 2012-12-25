package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

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
