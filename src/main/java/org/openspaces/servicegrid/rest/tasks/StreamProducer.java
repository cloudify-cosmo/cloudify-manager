package org.openspaces.servicegrid.rest.tasks;

import java.net.URL;

public interface StreamProducer<T> {

	URL addFirstElement(URL streamId, T element);
	
	URL addElement(URL streamId, T element);
	
}
