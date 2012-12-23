package org.openspaces.servicegrid.streams;

import java.net.URL;

public interface StreamProducer<T> {

	URL addFirstElement(URL streamId, T element);
	
	URL addElement(URL streamId, T element);
	
}
