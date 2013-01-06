package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.StartServiceInstanceTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class AgentTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state = new TaskExecutorState();
	private final Agent agent;

	public AgentTaskExecutor(Agent agent) {
		this.agent = agent;
	}
	
	@Override
	public void execute(Task task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof InstallServiceInstanceTask){
			agent.installServiceInstance((InstallServiceInstanceTask) task, impersonatedStateModifier);
		} else if (task instanceof StartServiceInstanceTask){
			agent.startServiceInstance((StartServiceInstanceTask) task, impersonatedStateModifier);
		}

	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}

}
