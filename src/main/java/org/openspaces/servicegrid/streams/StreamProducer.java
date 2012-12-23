package org.openspaces.servicegrid.streams;

import java.net.URL;

public interface StreamProducer<T> {
	
	URL addElement(URL streamId, T element);
	
}
