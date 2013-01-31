package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Collection;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.openspaces.servicegrid.streams.StreamWriter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.datatype.guava.GuavaModule;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.Iterables;
import com.google.common.collect.Multimap;
    
public class MockStreams<T> implements StreamWriter<T>, StreamReader<T> {

	private final Multimap<URI,String> streamById;
	private final ObjectMapper mapper;
	private final Logger logger;
	private boolean loggingEnabled;
	
	MockStreams() {
		logger = LoggerFactory.getLogger(this.getClass());
		streamById = ArrayListMultimap.create();
		mapper = new ObjectMapper();
		mapper.registerModule(new GuavaModule());
		mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
		mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
	}
	
	/**
	 * HTTP POST
	 */
	@Override
	public URI addElement(URI streamId, T element) {
		
		final Collection<String> stream = getStreamById(streamId);
		final URI elementId = getElementURIByIndex(streamId, stream.size() -1);
		if (element instanceof Task) {
			Task task = (Task) element;
			task.setTarget(streamId);
		}
		stream.add(StreamUtils.toJson(mapper, element));
		
		if (isLoggingEnabled() && logger.isInfoEnabled()) {
			String header = "POST "+ streamId.getPath() + " HTTP 1.1";
			try {
				String body = mapper.writeValueAsString(element);
				logger.info(header +"\n"+ body);
			} catch (JsonProcessingException e) {
				logger.warn(header,e);
			}
		}
		return elementId;
	}

	private Integer getIndex(final URI elementId, final URI streamId) {
		
		Preconditions.checkNotNull(streamId);
		String fixedStreamURI = streamIdToExternalForm(streamId);
		final Collection<?> stream = getStreamById(newURI(fixedStreamURI));
		String lastTaskURI = elementId == null ? null : elementId.toString();
		
		Preconditions.checkArgument(
				elementId == null || lastTaskURI.startsWith(fixedStreamURI),
				"%s is not related to %s",elementId ,streamId);
		
		Integer index = null;
		if (elementId != null) { 
			final String indexString = lastTaskURI.substring(fixedStreamURI.length());
			
			try {
				index = Integer.valueOf(indexString);
				Preconditions.checkElementIndex(index, stream.size(),"index " + index +" is too big for an array of size " + stream.size() + " elementId="+elementId+" streamId="+streamId);
			}
			catch (final NumberFormatException e) {
				Preconditions.checkArgument(false, "URI %s is invalid", elementId);
			}
		}
		return index;
	}

	private URI getElementURIByIndex(URI streamId, int index) {
		String URI = streamIdToExternalForm(streamId) + index;
		return newURI(URI);
	}

	private String streamIdToExternalForm(URI streamId) {
		Preconditions.checkNotNull(streamId);
		String externalForm = streamId.toString();
		if (!externalForm.endsWith("/")) {
			externalForm += "/";
		}
		return externalForm;
	}

	private static URI newURI(String URI) {
		try {
			return new URI(URI);
		} catch (final URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}

	/**
	 * HTTP GET /index
	 */
	@Override
	public <G extends T> G getElement(URI elementId, Class<G> clazz) {
		
		Preconditions.checkNotNull(elementId);
		Preconditions.checkNotNull(clazz);
		final URI streamId = getStreamId(elementId);
		
		Integer index = getIndex(elementId, streamId);
		Preconditions.checkNotNull(index);
		
		@SuppressWarnings("unchecked")
		G task = (G) getByIndex(streamId, index, clazz);
		
		return task;
	}

	private URI getStreamId(URI elementId) {
		Preconditions.checkNotNull(elementId);
		String string = elementId.toString();
		int seperator = string.lastIndexOf("/");
		Preconditions.checkPositionIndex(seperator, string.length());
		return newURI(string.substring(0,seperator+1));
	}
	
	private T getByIndex(URI streamId, int index, Class<? extends T> clazz) {
		final Collection<String> stream = getStreamById(streamId);
		return StreamUtils.fromJson(mapper, Iterables.get(stream,index), clazz);
	}

	@Override
	public URI getNextElementId(URI elementId) {
		Preconditions.checkNotNull(elementId);
		URI nextId = null;
		URI streamId = getStreamId(elementId);
		Integer index = getIndex(elementId,streamId);
		Preconditions.checkNotNull(index);
		Collection<?> stream = getStreamById(streamId);
		int nextIndex = index+1;
		if (nextIndex < stream.size() ) {
			nextId = getElementURIByIndex(streamId, nextIndex);
		}
		return nextId;
	}
	
	private Collection<String> getStreamById(URI streamId) {
		URI fixedStreamId = newURI(streamIdToExternalForm(streamId));
		return streamById.get(fixedStreamId);
	}

	@Override
	public URI getFirstElementId(URI streamId) {
		Preconditions.checkNotNull(streamId);
		Collection<?> stream = getStreamById(streamId);
		Preconditions.checkNotNull(stream);
		if (stream.isEmpty()) {
			return null;
		}
		return getElementURIByIndex(streamId , 0);
	}

	@Override
	public URI getLastElementId(URI streamId) {
		Preconditions.checkNotNull(streamId);
		Collection<?> stream = getStreamById(streamId);
		Preconditions.checkNotNull(stream);
		if (stream.isEmpty()) {
			return null;
		}
		return getElementURIByIndex(streamId , stream.size()-1);
	}

	public Iterable<URI> getElementIdsStartingWith(final URI URI) {
		
		final String URIPrefix = streamIdToExternalForm(URI);
		return Iterables.filter(streamById.keySet(), new Predicate<URI>() {

			@Override
			public boolean apply(URI streamId) {
				return streamIdToExternalForm(streamId).startsWith(URIPrefix);
			}
		});
	}
	
	public void clear() {
		this.streamById.clear();
	}

	public boolean isLoggingEnabled() {
		return loggingEnabled;
	}

	public void setLoggingEnabled(boolean loggingEnabled) {
		this.loggingEnabled = loggingEnabled;
	}

	public ObjectMapper getMapper() {
		return mapper;
	}
}
