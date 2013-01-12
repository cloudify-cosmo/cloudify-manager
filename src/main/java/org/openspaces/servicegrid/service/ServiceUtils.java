package org.openspaces.servicegrid.service;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceUtils {
	
	public static Iterable<URI> getExecutingAndPendingTasks(StreamReader<TaskConsumerState> stateReader, StreamReader<Task> taskReader, URI executorId) {
		 return Iterables.concat(
				 getExecutingTasks(stateReader, executorId), 
				 getPendingTasks(stateReader, taskReader, executorId));
	}
	
	public static Iterable<URI> getExecutingTasks(StreamReader<TaskConsumerState> stateReader, URI executorId) {
		TaskConsumerState taskConsumerState = StreamUtils.getLastElement(stateReader, executorId, TaskConsumerState.class);
		if (taskConsumerState == null) {
			return Lists.newArrayList();
		}
		return taskConsumerState.getExecutingTasks();
	}
	
	public static Iterable<URI> getPendingTasks(StreamReader<TaskConsumerState> stateReader, StreamReader<Task> taskReader,URI id) {

		List<URI> tasks = Lists.newArrayList();
		URI pendingTaskId = getNextTaskToConsume(stateReader, taskReader, id);
		while (pendingTaskId != null) {
			tasks.add(pendingTaskId);
			pendingTaskId = taskReader.getNextElementId(pendingTaskId);
		}
		return tasks;
	}
	
	public static URI getNextTaskToConsume(StreamReader<TaskConsumerState> stateReader, StreamReader<Task> taskReader, URI executorId) {
		URI lastTask = null;
		
		final TaskConsumerState state = StreamUtils.getLastElement(stateReader, executorId, TaskConsumerState.class);
		if (state != null) {
			lastTask = Iterables.getLast(state.getCompletedTasks(),null);
		}
		
		URI nextTask = null;
		if (lastTask == null) {
			nextTask = taskReader.getFirstElementId(executorId);
		}
		else {
			nextTask = taskReader.getNextElementId(lastTask); 
		}
		
		return nextTask;
	}
}
