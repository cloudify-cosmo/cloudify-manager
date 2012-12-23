package org.openspaces.servicegrid.rest.tasks;

import java.net.URL;

public interface StreamConsumer<T> {

	URL getFirstId(URL streamId);
	
	URL getNextId(URL taskId);

	T getById(URL taskId);

}
