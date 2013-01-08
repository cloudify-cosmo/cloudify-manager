package org.openspaces.servicegrid.streams;

import java.net.URI;

public interface StreamProducer<T> {
	
	URI addElement(URI streamId, T element);
	
}
