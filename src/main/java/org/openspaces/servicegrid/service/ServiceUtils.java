package org.openspaces.servicegrid.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.mock.MockTaskBroker;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceUtils {
	
	public static Iterable<Task> getExecutingAndPendingTasks(
			final StateReader stateReader, 
			final TaskReader taskReader, 
			final URI taskConsumerId) {
		
		return Iterables.concat(
				getExecutingTasks(stateReader, taskConsumerId), 
				taskReader.getPendingTasks(taskConsumerId));
	}

	private static Iterable<Task> getExecutingTasks(final StateReader stateReader,
			final URI taskConsumerId) {
		List<Task> executingTasks = Lists.newArrayList();
		EtagState<TaskConsumerState> etagState = stateReader.get(taskConsumerId, TaskConsumerState.class);
		if (etagState != null) {
			final Task executingTask = etagState.getState().getExecutingTask();
			if (executingTask != null) {
				executingTasks.add(executingTask);
			}
		}
		return executingTasks;
	}

	public static boolean isTaskExecutingOrPending(
			final StateReader stateReader, 
			final TaskReader taskReader, 
			final Task newTask) {
			
		final MockTaskBroker taskBroker = (MockTaskBroker)taskReader;
		final URI taskConsumerId = newTask.getConsumerId();
		return 
			Iterables.tryFind(getExecutingAndPendingTasks(stateReader, taskReader, taskConsumerId),
				new Predicate<Task>() {
					@Override
					public boolean apply(final Task existingTask) {
						Preconditions.checkNotNull(existingTask);
						Preconditions.checkArgument(taskConsumerId.equals(existingTask.getConsumerId()),"Expected target " + taskConsumerId + " actual target " + existingTask.getConsumerId());
						return taskBroker.tasksEqualsIgnoreTimestampIgnoreSource(existingTask, newTask);
				}}
			).isPresent();
		
	}
	
	public static AgentState getAgentState(
			final StateReader stateReader, 
			final URI agentId) {
		EtagState<AgentState> etagState = stateReader.get(agentId, AgentState.class);
		return etagState == null ? null : etagState.getState();
	}

	public static ServiceState getServiceState(
			final StateReader stateReader,
			final URI serviceId) {
		EtagState<ServiceState> etagState = stateReader.get(serviceId, ServiceState.class);
		return etagState == null ? null : etagState.getState();
	}
	
	public static ServiceInstanceState getServiceInstanceState(
			final StateReader stateReader, 
			final URI instanceId) {
		EtagState<ServiceInstanceState> etagState = stateReader.get(instanceId, ServiceInstanceState.class);
		return etagState == null ? null : etagState.getState();
	}
	
	public static URI toTasksURI(final URI taskConsumerId) {
		try {
			return new URI(taskConsumerId.toString() + "tasks/");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}
		
	public static URI newTasksId(URI tasks, Integer start, Integer end) {
		Preconditions.checkArgument(start != null || end != null);
		StringBuilder uri = new StringBuilder();
		uri.append(tasks.toString());
		if (start != null) {
			uri.append(start);
		}
		uri.append("..");
		if (end != null) {
			uri.append(end);
		}
		try {
			return new URI(uri.toString());
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}

	public static URI newTaskId(URI postNewTask, int taskIndex) {
		StringBuilder uri = new StringBuilder();
		uri.append(postNewTask.toString()).append(taskIndex);
		try {
			return new URI(uri.toString());
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}
}
