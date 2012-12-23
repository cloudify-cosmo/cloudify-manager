package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface ImpersonatingTaskExecutor<S extends TaskExecutorState> {

	void execute(Task task, TaskExecutorStateModifier impersonatedStateModifier);
	
	S getState();
}
