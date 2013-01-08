package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.StartServiceInstanceTask;
import org.openspaces.servicegrid.model.task.PingTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.base.Preconditions;

public class AgentTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> , TaskExecutor<TaskExecutorState> {

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
		} else {
			Preconditions.checkState(false, "Cannot handle task " + task.getClass());
		}
	}

	@Override
	public TaskExecutorState getState() {
		return state;
	}

	@Override
	public void execute(Task task) {
		if (task instanceof PingTask){
			//do nothing
		}
		else {
			Preconditions.checkState(false, "Cannot handle task " + task.getClass());
		}
	}

}
