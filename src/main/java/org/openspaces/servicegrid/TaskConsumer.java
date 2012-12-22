package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;

public interface TaskConsumer {

	Iterable<URL> listTaskIds(URL executorId, URL lastTaskId);
	
	Task get(URL taskId);
}
