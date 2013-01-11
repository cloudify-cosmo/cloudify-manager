package org.openspaces.servicegrid.streams;

import java.net.URI;

public interface StreamWriter<T> {
	
	URI addElement(URI streamId, T element);
	
}
