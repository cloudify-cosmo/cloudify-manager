package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Collection;

import org.codehaus.jackson.map.ObjectMapper;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.Iterables;
import com.google.common.collect.Multimap;

public class MockStreams<T> implements StreamProducer<T>, StreamConsumer<T> {

	final private Multimap<URI,T> streamById = ArrayListMultimap.create();
	final private ObjectMapper mapper = new ObjectMapper();
	
	/**
	 * HTTP POST
	 */
	@Override
	public URI addElement(URI streamId, T element) {
		
		final Collection<T> stream = getStreamById(streamId);
		stream.add(clone(element));
		final URI elementId = getElementURIByIndex(streamId, stream.size() -1);
		return elementId;
	}

	private T clone(T element) {
		try {
			@SuppressWarnings("unchecked")
			T clone = (T)mapper.readValue(mapper.writeValueAsBytes(element), element.getClass());
			return clone;
		} catch (Exception e) {
			throw Throwables.propagate(e);
		}
	}

	private Integer getIndex(final URI elementId, final URI streamId) {
		
		Preconditions.checkNotNull(streamId);
		String fixedStreamURI = streamIdToExternalForm(streamId);
		final Collection<T> stream = getStreamById(newURI(fixedStreamURI));
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
		G task = (G) getByIndex(streamId, index);
		Preconditions.checkNotNull(task);
		@SuppressWarnings("unchecked")
		G clonedTask = (G) clone(task);
		return clonedTask;
	}

	private URI getStreamId(URI elementId) {
		Preconditions.checkNotNull(elementId);
		String string = elementId.toString();
		int seperator = string.lastIndexOf("/");
		Preconditions.checkPositionIndex(seperator, string.length());
		return newURI(string.substring(0,seperator+1));
	}
	
	private T getByIndex(URI streamId, int index) {
		final Collection<T> stream = getStreamById(streamId);
		if (index >= stream.size()) {
			return null;
		}
		return Iterables.get(stream,index);
	}

	@Override
	public URI getNextElementId(URI elementId) {
		Preconditions.checkNotNull(elementId);
		URI nextId = null;
		URI streamId = getStreamId(elementId);
		Integer index = getIndex(elementId,streamId);
		Preconditions.checkNotNull(index);
		Collection<T> stream = getStreamById(streamId);
		int nextIndex = index+1;
		if (nextIndex < stream.size() ) {
			nextId = getElementURIByIndex(streamId, nextIndex);
		}
		return nextId;
	}
	
	private Collection<T> getStreamById(URI streamId) {
		URI fixedStreamId = newURI(streamIdToExternalForm(streamId));
		return streamById.get(fixedStreamId);
	}

	@Override
	public URI getFirstElementId(URI streamId) {
		Preconditions.checkNotNull(streamId);
		Collection<T> stream = getStreamById(streamId);
		Preconditions.checkNotNull(stream);
		if (stream.isEmpty()) {
			return null;
		}
		return getElementURIByIndex(streamId , 0);
	}

	@Override
	public URI getLastElementId(URI streamId) {
		Preconditions.checkNotNull(streamId);
		Collection<T> stream = getStreamById(streamId);
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
	
	public Iterable<URI> getElementIds() {
		return Iterables.unmodifiableIterable(streamById.keySet());
	}

}
