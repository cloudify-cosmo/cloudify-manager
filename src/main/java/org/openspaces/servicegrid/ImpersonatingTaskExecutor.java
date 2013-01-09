package org.openspaces.servicegrid;


public interface ImpersonatingTaskExecutor<S extends TaskExecutorState> {

	void execute(Task task, TaskExecutorStateModifier impersonatedStateModifier);
	
	S getState();
}
