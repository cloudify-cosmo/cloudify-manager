package org.openspaces.servicegrid.state;

import java.net.URI;

public interface StateReader {

	<T> EtagState<T> get(URI id, Class<? extends T> clazz);

	Iterable<URI> getElementIdsStartingWith(URI idPrefix);
}
