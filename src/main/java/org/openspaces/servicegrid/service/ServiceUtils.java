package org.openspaces.servicegrid.service;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.openspaces.servicegrid.streams.StreamWriter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
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

	public static URI getExistingTaskId( 
			final StreamReader<TaskConsumerState> stateReader, 
			final StreamReader<Task> taskReader, 
			final Task newTask) {
		
		final ObjectMapper taskMapper = ((MockStreams<?>)taskReader).getMapper();
		final URI agentId = newTask.getTarget();
		final URI existingTaskId = 
			Iterables.find(getExecutingAndPendingTasks(stateReader, taskReader, agentId),
				new Predicate<URI>() {
					@Override
					public boolean apply(final URI existingTaskId) {
						final Task existingTask = taskReader.getElement(existingTaskId, Task.class);
						Preconditions.checkArgument(agentId.equals(existingTask.getTarget()),"Expected target " + agentId + " actual target " + existingTask.getTarget());
						return tasksEqualsIgnoreTimestampIgnoreSource(taskMapper, existingTask, newTask);
				}},
				null
			);
		return existingTaskId;
	}
	
	private static boolean tasksEqualsIgnoreTimestampIgnoreSource(
			final ObjectMapper mapper, 
			final Task task1, 
			final Task task2) {
		
		if (!task1.getClass().equals(task2.getClass())) {
			return false;
		}
		final Task task1Clone = StreamUtils.cloneElement(mapper, task1);
		final Task task2Clone = StreamUtils.cloneElement(mapper, task2);
		task1Clone.setSourceTimestamp(null);
		task2Clone.setSourceTimestamp(null);
		task1Clone.setSource(null);
		task2Clone.setSource(null);
		return StreamUtils.elementEquals(mapper, task1Clone, task2Clone);
	
	}
	
	public static AgentState getAgentState(
			final StreamReader<TaskConsumerState> stateReader, 
			final URI agentId) {
		return StreamUtils.getLastElement(stateReader, agentId, AgentState.class);
	}

	public static ServiceState getServiceState(
			final StreamReader<TaskConsumerState> stateReader,
			final URI serviceId) {
		ServiceState serviceState = StreamUtils.getLastElement(stateReader, serviceId, ServiceState.class);
		return serviceState;
	}
	
	public static ServiceInstanceState getServiceInstanceState(
			final StreamReader<TaskConsumerState> stateReader, 
			final URI instanceId) {
		return StreamUtils.getLastElement(stateReader, instanceId, ServiceInstanceState.class);
	}
	
	public static URI getNextTaskId(
			final TaskConsumerState state, 
			final StreamReader<Task> taskReader, 
			final URI taskConsumerId) {
		
		Preconditions.checkNotNull(state);
		final URI lastTaskId = getLastTaskIdOrNull(state);
		URI taskId;
		if (lastTaskId == null) {
			taskId = taskReader.getFirstElementId(taskConsumerId);
		}
		else {
			taskId = taskReader.getNextElementId(lastTaskId);
		}
		return taskId;
	}

	private static URI getLastTaskIdOrNull(final TaskConsumerState state) {
		return Iterables.getLast(Iterables.concat(state.getCompletedTasks(),state.getExecutingTasks()), null);
	}

	public static void addTask(
			final StreamWriter<Task> taskWriter,
			final URI taskConsumerId, 
			final Task task) {
		
		Preconditions.checkNotNull(taskWriter);
		Preconditions.checkNotNull(taskConsumerId);
		Preconditions.checkNotNull(task);

		taskWriter.addElement(taskConsumerId, task);
	}
}
