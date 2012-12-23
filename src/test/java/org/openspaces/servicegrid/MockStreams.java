package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.Collection;
import java.util.regex.Pattern;

import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.Iterables;
import com.google.common.collect.Multimap;

public class MockStreams<T> implements StreamProducer<T>, StreamConsumer<T> {

	Multimap<URL,T> streamById = ArrayListMultimap.create();
	
	/**
	 * HTTP POST
	 */
	@Override
	public URL addElement(URL streamId, T element) {
		
		final Collection<T> stream = streamById.get(streamId);
		stream.add(element);
		final URL elementId = getTaskUrl(streamId, stream.size() -1);
		return elementId;
	}

	private Integer getIndex(final URL elementId, final URL streamId) {
		
		Preconditions.checkNotNull(streamId);
		final Collection<T> stream = streamById.get(streamId);
		String lastTaskUrl = elementId == null ? null : elementId.toExternalForm();
		String tasksRootUrl = streamId.toExternalForm() + "tasks/";
		
		Preconditions.checkArgument(
				elementId == null || lastTaskUrl.startsWith(tasksRootUrl),
				"%s is not related to %s",elementId ,streamId);
		
		Integer index = null;
		if (elementId != null) { 
			final String indexString = lastTaskUrl.substring(tasksRootUrl.length());
			
			try {
				index = Integer.valueOf(indexString);
				Preconditions.checkElementIndex(index, stream.size());
			}
			catch (final NumberFormatException e) {
				Preconditions.checkArgument(false, "URL %s is invalid", elementId);
			}
		}
		return index;
	}

	private URL getTaskUrl(URL streamId, int index) {
		String url = streamId.toExternalForm() + "tasks/" + index;
		return newUrl(url);
	}

	private static URL newUrl(String url) {
		try {
			return new URL(url);
		} catch (final MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}

	/**
	 * HTTP GET /index
	 */
	@Override
	public T getElement(URL elementId) {
		
		final URL streamId = getStreamId(elementId);
		
		Integer index = getIndex(elementId, streamId);
		Preconditions.checkNotNull(index);
		
		T task = getByIndex(streamId, index);
		Preconditions.checkNotNull(task);
		return task;
	}

	private URL getStreamId(URL elementId) {
		final String[] split = elementId.toExternalForm().split(Pattern.quote("tasks/"));
		Preconditions.checkElementIndex(0, split.length);
		final URL executorId = newUrl(split[0]);
		return executorId;
	}
	
	private T getByIndex(URL streamId, int index) {
		final Collection<T> stream = streamById.get(streamId);
		if (stream.size() <= index) {
			return null;
		}
		return Iterables.get(stream,index);
	}

	@Override
	public URL getNextElementId(URL elementId) {
		Preconditions.checkNotNull(elementId);
		URL nextId = null;
		URL streamId = getStreamId(elementId);
		Integer index = getIndex(elementId,streamId);
		Preconditions.checkNotNull(index);
		Collection<T> stream = streamById.get(streamId);
		if (stream.size() > index+1) {
			nextId = getTaskUrl(streamId, index+1);
		}
		return nextId;
	}

	@Override
	public URL getFirstElementId(URL streamId) {
		Preconditions.checkNotNull(streamId);
		Collection<T> stream = streamById.get(streamId);
		Preconditions.checkNotNull(stream);
		if (stream.isEmpty()) {
			return null;
		}
		return getTaskUrl(streamId , 0);
	}

	@Override
	public URL getLastElementId(URL streamId) {
		Preconditions.checkNotNull(streamId);
		Collection<T> stream = streamById.get(streamId);
		Preconditions.checkNotNull(stream);
		if (stream.isEmpty()) {
			return null;
		}
		return getTaskUrl(streamId , stream.size()-1);
	}

}
