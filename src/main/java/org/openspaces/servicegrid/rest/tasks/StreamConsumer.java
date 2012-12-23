package org.openspaces.servicegrid.rest.tasks;

import java.net.URL;

public interface StreamConsumer<T> {

	URL getFirstElementId(URL streamId);
	
	URL getNextElementId(URL elementId);
	
	URL getLastElementId(URL streamId);

	T getElement(URL elementId);

}
