package org.openspaces.servicegrid.kvstore;

import java.net.URI;

import javax.ws.rs.core.EntityTag;

public interface KVWriter {

	EntityTag put(URI key, String state);
}
