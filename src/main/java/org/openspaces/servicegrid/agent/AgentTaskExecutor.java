package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;

import com.google.common.base.Preconditions;

public class AgentTaskExecutor implements
		ImpersonatingTaskExecutor<TaskExecutorState> , TaskExecutor<TaskExecutorState> {

	private final AgentState state = new AgentState();
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
		if (task instanceof PingAgentTask){
			//do nothing
		}
		else {
			Preconditions.checkState(false, "Cannot handle task " + task.getClass());
		}
	}

}
