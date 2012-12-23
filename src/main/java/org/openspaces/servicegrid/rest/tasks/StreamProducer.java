package org.openspaces.servicegrid.rest.tasks;

import java.net.URL;

public interface StreamProducer<T> {

	void createStream(URL streamId);
	
	URL addToStream(URL streamId, T object);
	
}
