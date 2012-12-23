package org.openspaces.servicegrid.rest.tasks;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;

public interface StreamConsumer {

	URL getFirstId(URL streamId);
	
	URL getNextId(URL taskId);

	Task getById(URL taskId);

}
