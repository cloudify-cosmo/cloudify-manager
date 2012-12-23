package org.openspaces.servicegrid.rest.tasks;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;

public interface StreamProducer {

	void createStream(URL streamId);
	
	URL addToStream(URL streamId, Task object);
	
}
