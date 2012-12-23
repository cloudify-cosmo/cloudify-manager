package org.openspaces.servicegrid.streams;

import java.net.URL;

public interface StreamConsumer<T> {

	URL getFirstElementId(URL streamId);
	
	URL getNextElementId(URL elementId);
	
	URL getLastElementId(URL streamId);

	<G extends T> G getElement(URL elementId);

}
