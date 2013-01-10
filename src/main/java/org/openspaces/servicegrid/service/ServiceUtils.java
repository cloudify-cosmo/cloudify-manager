package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.streams.StreamConsumer;

public class ServiceUtils {
	
	public static <T> T getLastState(StreamConsumer<? super T> stateReader, URI executorId, Class<T> clazz) {
		T executorState = null;
		URI lastAgentStateId = stateReader.getLastElementId(executorId);
		if (lastAgentStateId != null) {
			executorState = stateReader.getElement(lastAgentStateId, clazz);
		}
		return executorState;
	}
}
