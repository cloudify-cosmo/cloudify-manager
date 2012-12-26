package org.openspaces.servicegrid.mock;

import java.net.URL;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface TaskExecutorWrapper {
	
	void wrapTaskExecutor(TaskExecutor<? extends TaskExecutorState> taskExecutor, URL executorId);
	
	void wrapImpersonatingTaskExecutor(ImpersonatingTaskExecutor<? extends TaskExecutorState> impersonatingTaskExecutor, URL executorId);
	
}
