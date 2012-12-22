package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.List;
import java.util.Map;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.rest.HttpError;
import org.openspaces.servicegrid.rest.HttpException;
import org.openspaces.servicegrid.rest.NotFoundHttpException;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

public class MapTaskBroker implements TaskProducer, TaskConsumer {

	Map<URL, Task> tasksPerId = Maps.newHashMap();
	Map<URL, Integer> numberOfTasksPerExecutorId = Maps.newHashMap();

	@Override
	public URL post(URL executorId, Task task) {
		
		if (task.getTarget() == null || !task.getTarget().equals(executorId)) {
			throw new HttpException(HttpError.BAD_REQUEST);
		}
		
		Integer numberOfTasks = numberOfTasksPerExecutorId.get(executorId);
		if (numberOfTasks == null) {
			numberOfTasks = 0;
		}
		numberOfTasks++;
		numberOfTasksPerExecutorId.put(executorId, numberOfTasks);
		URL taskId = newTaskUrl(executorId, numberOfTasks-1);
		tasksPerId.put(taskId, task);
		return taskId;
	}

	@Override
	public Iterable<URL> listTaskIds(final URL executorId, URL lastTaskId) {
		Preconditions.checkNotNull(executorId);
		
		String lastTaskUrl = lastTaskId == null ? null : lastTaskId.toExternalForm();
		String tasksRootUrl = executorId.toExternalForm() + "tasks/";
		
		Preconditions.checkArgument(
				lastTaskId == null || lastTaskUrl.startsWith(tasksRootUrl),
				"%s is not related to %s",lastTaskId ,executorId);
		
		Integer numberOfTasks = numberOfTasksPerExecutorId.get(executorId);
		if (numberOfTasks == null) {
			numberOfTasks = 0;
		}
		Integer index = null;
		if (lastTaskId != null) { 
			String indexString = lastTaskUrl.substring(tasksRootUrl.length());
			try {
				index = Integer.valueOf(indexString);
				Preconditions.checkElementIndex(index, numberOfTasks);
			}
			catch (NumberFormatException e) {
				Preconditions.checkArgument(false, "URL %s is invalid", lastTaskId);
			}
		}
		if (index == null) {
			index = -1;
		}
		
		List<URL> newTaskIds = Lists.newLinkedList();
		for (index++ ; index < numberOfTasks ; index++) {
			newTaskIds.add(newTaskUrl(executorId, index));
		}
		return Iterables.unmodifiableIterable(newTaskIds);
	}

	private static URL newTaskUrl(URL executorId, int index) {
		try {
			return new URL(executorId.toExternalForm() + "tasks/" + index);
		} catch (final MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}

	@Override
	public Task get(URL taskId) {
		if (taskId == null) {
			throw new HttpException(HttpError.BAD_REQUEST);
		}
		Task task = tasksPerId.get(taskId);
		if (task == null) {
			throw new NotFoundHttpException(taskId); 
		}
		return task;
	}
	
}
