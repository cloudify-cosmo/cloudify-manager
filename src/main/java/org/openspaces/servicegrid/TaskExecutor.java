package org.openspaces.servicegrid;


public interface TaskExecutor<S extends TaskExecutorState> {

	void execute(Task task);
	
	S getState();
}
