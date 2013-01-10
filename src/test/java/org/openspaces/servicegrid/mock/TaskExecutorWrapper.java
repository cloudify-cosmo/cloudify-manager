package org.openspaces.servicegrid.mock;

import java.net.URI;

public interface TaskExecutorWrapper {
	
	void wrapTaskExecutor(Object taskExecutor, URI executorId);

	void removeTaskExecutor(URI executorId);
	
}
