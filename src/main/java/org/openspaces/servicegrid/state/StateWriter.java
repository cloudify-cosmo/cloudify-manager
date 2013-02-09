package org.openspaces.servicegrid.state;

import java.net.URI;

public interface StateWriter {

	/**
	 * Sets the state of the specified id to the specified state, if the current state matches the specified etag.
	 * If there is no match, an exception is raised
	 * If there is no current state, then ifMatches must be {@link Etag#EMPTY}
	 * @return the etag if the new state
	 */
	Etag put(URI id, Object state, Etag ifMatchHeader) throws EtagPreconditionNotMetException;
}
