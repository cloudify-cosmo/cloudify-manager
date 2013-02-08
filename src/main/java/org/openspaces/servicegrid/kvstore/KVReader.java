package org.openspaces.servicegrid.kvstore;

import java.net.URI;

import javax.ws.rs.core.EntityTag;

import org.openspaces.servicegrid.kvstore.KVStore.EntityTagState;

import com.google.common.base.Optional;

public interface KVReader {

	Optional<EntityTagState<String>> getState(URI key);
	Optional<EntityTag> getEntityTag(URI key);
	Iterable<URI> listKeysStartsWith(URI newURI);

}
