package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.state.EtagPreconditionNotMetException;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.beust.jcommander.internal.Maps;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;

public class MockState implements StateReader, StateWriter {
	
	private final Logger logger;
	private final ObjectMapper mapper;
	private final Map<URI, EtagState<String>> stateById;
	private boolean loggingEnabled;
	
	public MockState() {
		logger = LoggerFactory.getLogger(this.getClass());
		mapper = StreamUtils.newObjectMapper();
		stateById = Maps.newLinkedHashMap();
	}
	
	@Override
	public Etag put(URI id, Object state, Etag ifMatchHeader) {
		final URI key = StreamUtils.fixSlash(id);
		
		final EtagState<String> oldState = stateById.get(key);
		final Etag oldEtag = oldState == null ? Etag.EMPTY : oldState.getEtag();
		if (!ifMatchHeader.equals(oldEtag)) {
			if (isLoggingEnabled() && logger.isInfoEnabled()) {
				final String request = "PUT "+ id.getPath() + " HTTP 1.1\nIf-Match:"+ifMatchHeader+"\n"+StreamUtils.toJson(mapper,state);
				final String response = "HTTP/1.1 412 Precondition Failed";
				logger.info(request +"\n"+ response+"\n");
			}
			throw new EtagPreconditionNotMetException(oldEtag, ifMatchHeader);
		} 

		EtagState<String> etagState = createEtagState(state);
		stateById.put(key, etagState);
		if (isLoggingEnabled() && logger.isInfoEnabled()) {
			final String request = "PUT "+ id.getPath() + " HTTP 1.1\nIf-Match:"+ifMatchHeader+"\n"+etagState.getState();
			final String response = "HTTP/1.1 200 Ok\nETag: "+etagState.getEtag() ;
			logger.info(request +"\n"+ response+"\n");
		}
		return etagState.getEtag();

	}

	private EtagState<String> createEtagState(Object state) {
		final String json = StreamUtils.toJson(mapper,state);
		final Etag etag = Etag.create(json);
		final EtagState<String> etagState = new EtagState<String>(etag, json);
		return etagState;
	}


	@Override
	public <T> EtagState<T> get(URI id, Class<? extends T> clazz) {
		final URI key = StreamUtils.fixSlash(id);
		final EtagState<String> etagState = stateById.get(key);
		if (etagState == null) {
			if (isLoggingEnabled() && logger.isInfoEnabled()) {
				final String request = "GET "+ id.getPath() + " HTTP 1.1";
				final String response = "HTTP/1.1 404 Not Found";
				logger.info(request +"\n"+ response+"\n");
			}
			return null;
		}
		
		final T state = StreamUtils.fromJson(mapper, etagState.getState(), clazz);
		
		if (isLoggingEnabled() && logger.isInfoEnabled()) {
			final String request = "GET "+ id.getPath() + " HTTP 1.1";
			try {
				final String response = "HTTP/1.1 200 Ok\nETag: "+etagState.getEtag()+"\n" + mapper.writeValueAsString(state);
				logger.info(request +"\n"+ response+"\n");
			} catch (JsonProcessingException e) {
				logger.warn(request,e);
			}
		}
		
		return new EtagState<T>(etagState.getEtag(), state);
	}

	public boolean isLoggingEnabled() {
		return loggingEnabled;
	}

	public void setLoggingEnabled(boolean loggingEnabled) {
		this.loggingEnabled = loggingEnabled;
	}

	public boolean stateEquals(TaskConsumerState state1, TaskConsumerState state2) {
		return StreamUtils.elementEquals(mapper, state1, state2);
	}

	/**
	 * Simulates process restart
	 */
	public void clear() {
		stateById.clear();
	}

	@Override
	public Iterable<URI> getElementIdsStartingWith(final URI idPrefix) {
		return Iterables.filter(stateById.keySet(), new Predicate<URI>(){

			@Override
			public boolean apply(URI id) {
				return id.toString().startsWith(idPrefix.toString());
			}});
	}

}
