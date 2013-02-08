package org.openspaces.servicegrid.kvstore;

import java.net.URI;

import javax.ws.rs.core.EntityTag;

public interface KVReader {

	String getState(URI key);
	EntityTag getEntityTag(URI key);
	Iterable<URI> listKeysStartsWith(URI newURI);

}
