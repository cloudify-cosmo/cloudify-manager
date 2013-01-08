package org.openspaces.servicegrid.streams;

import java.net.URI;

public interface StreamConsumer<T> {

	URI getFirstElementId(URI streamId);
	
	URI getNextElementId(URI elementId);
	
	URI getLastElementId(URI streamId);

	<G extends T> G getElement(URI elementId, Class<G> clazz);

}
