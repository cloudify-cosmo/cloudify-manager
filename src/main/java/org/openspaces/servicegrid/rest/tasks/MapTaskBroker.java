package org.openspaces.servicegrid.rest.tasks;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.Collection;
import java.util.List;
import java.util.regex.Pattern;

import org.openspaces.servicegrid.model.tasks.Task;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Multimap;

public class MapTaskBroker implements TaskProducer, TaskConsumer {

	Multimap<URL,Task> streamById = ArrayListMultimap.create();
	
	@Override
	public URL post(URL executorId, Task task) {
		
		Collection<Task> stream = streamById.get(executorId);
		stream.add(task);
		URL taskId = newTaskUrl(executorId, stream.size() -1);
		return taskId;
	}

	@Override
	public Iterable<URL> listTaskIds(final URL executorId, URL lastTaskId) {
		
		Integer index = getIndex(lastTaskId, executorId);
		if (index == null) {
			index = -1;
		}
		
		final Collection<Task> stream = streamById.get(executorId);
		List<URL> newTaskIds = Lists.newLinkedList();
		for (index++ ; index < stream.size() ; index++) {
			newTaskIds.add(newTaskUrl(executorId, index));
		}
		return Iterables.unmodifiableIterable(newTaskIds);
	}

	private Integer getIndex(final URL taskId, final URL executorId) {
		
		Preconditions.checkNotNull(executorId);
		final Collection<Task> stream = streamById.get(executorId);
		String lastTaskUrl = taskId == null ? null : taskId.toExternalForm();
		String tasksRootUrl = executorId.toExternalForm() + "tasks/";
		
		Preconditions.checkArgument(
				taskId == null || lastTaskUrl.startsWith(tasksRootUrl),
				"%s is not related to %s",taskId ,executorId);
		
		Integer index = null;
		if (taskId != null) { 
			final String indexString = lastTaskUrl.substring(tasksRootUrl.length());
			try {
				index = Integer.valueOf(indexString);
				Preconditions.checkElementIndex(index, stream.size());
			}
			catch (final NumberFormatException e) {
				Preconditions.checkArgument(false, "URL %s is invalid", taskId);
			}
		}
		return index;
	}

	private static URL newTaskUrl(URL executorId, int index) {
		String url = executorId.toExternalForm() + "tasks/" + index;
		return newUrl(url);
	}

	private static URL newUrl(String url) {
		try {
			return new URL(url);
		} catch (final MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}

	@Override
	public Task get(URL taskId) {
		
		String[] split = taskId.toExternalForm().split(Pattern.quote("tasks/"));
		Preconditions.checkElementIndex(0, split.length);
		
		URL executorId = newUrl(split[0]);
		Integer index = getIndex(taskId, executorId);
		Preconditions.checkNotNull(index);
		
		Collection<Task> stream = streamById.get(executorId);
		Preconditions.checkPositionIndex(index, stream.size());
		return Iterables.get(stream,index);
	}
	
}
