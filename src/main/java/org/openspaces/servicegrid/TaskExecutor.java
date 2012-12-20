package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface TaskExecutor<S extends TaskExecutorState> {

	void execute(Task task);
	
	S getState();
	
	String getId();
	
}
