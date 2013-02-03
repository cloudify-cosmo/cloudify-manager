package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskProducerTask;
import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.TaskWriter;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.collect.Iterables;
import com.google.common.collect.LinkedListMultimap;

public class MockTaskBroker implements TaskReader, TaskWriter {

	private final Logger logger;
	private final ObjectMapper mapper;
	private final LinkedListMultimap<URI, String> streamById;
	private boolean loggingEnabled;

	public MockTaskBroker() {
		logger = LoggerFactory.getLogger(this.getClass());
		mapper = StreamUtils.newObjectMapper();
		streamById = LinkedListMultimap.create();
	}
	
	@Override
	public void postNewTask(Task task) {
		final URI key = StreamUtils.fixSlash(task.getConsumerId());
		final String json = StreamUtils.toJson(mapper,task);
		streamById.put(key, json);
		if (isLoggingEnabled() && logger.isInfoEnabled() && !(task instanceof TaskProducerTask)) {
			String request = "POST "+ key + " HTTP 1.1\n"+json;
			String response = "HTTP/1.1 202 Accepted";
			logger.info(request +"\n"+ response+"\n");
		}
	}

	@Override
	public <T extends Task> T removeNextTask(URI taskConsumerId) {
		final URI key = StreamUtils.fixSlash(taskConsumerId);
		final List<String> tasks = streamById.get(key);
		if (tasks.isEmpty()) {
			if (isLoggingEnabled() && logger.isInfoEnabled()) {
				String request = "DELETE "+ taskConsumerId.getPath() + "_first HTTP 1.1";
				String response = "HTTP/1.1 404 Not Found";
				logger.info(request +"\n"+ response+"\n");
			}
			return null;
		}
		
		final String removed = tasks.remove(0);
		final T task = (T) StreamUtils.fromJson(mapper, removed, Task.class);
		if (isLoggingEnabled() && logger.isInfoEnabled()) {
			String request = "DELETE "+ taskConsumerId.getPath() + "/_first HTTP 1.1";
			String response = "HTTP/1.1 200 OK\n"+removed;
			logger.info(request +"\n"+ response);
		}
		return task;
	}

	private boolean isLoggingEnabled() {
		return loggingEnabled;
	}

	public void setLoggingEnabled(boolean loggingEnabled) {
		this.loggingEnabled = loggingEnabled;
	}

	public boolean taskEquals(Task task1, Task task2) {
		return StreamUtils.elementEquals(mapper, task1, task2);
	}

	/**
	 * Simulates process restart
	 */
	public void clear() {
		streamById.clear();
	}

	@Override
	public Iterable<Task> getPendingTasks(URI taskConsumerId) {
		final URI key = StreamUtils.fixSlash(taskConsumerId);
		final List<String> jsonTasks = streamById.get(key);
		if (isLoggingEnabled() && logger.isInfoEnabled()) {
			String request = "GET "+ taskConsumerId.getPath() + "/ HTTP 1.1";
			String response = "HTTP/1.1 200 OK\n"+StreamUtils.toJson(mapper, jsonTasks);
			logger.info(request +"\n"+ response+"\n");
		}
		final Iterable<Task> tasks = Iterables.unmodifiableIterable(Iterables.transform(jsonTasks, new Function<String, Task>(){

			@Override
			public Task apply(String json) {
				return StreamUtils.fromJson(mapper, json, Task.class);
			}})
		);
		
		return tasks;
	}

	public ObjectMapper getMapper() {
		return null;
	}

	public boolean tasksEqualsIgnoreTimestampIgnoreSource(
			final Task task1, 
			final Task task2) {
		
		if (!task1.getClass().equals(task2.getClass())) {
			return false;
		}
		final Task task1Clone = StreamUtils.cloneElement(mapper, task1);
		final Task task2Clone = StreamUtils.cloneElement(mapper, task2);
		task1Clone.setProducerTimestamp(null);
		task2Clone.setProducerTimestamp(null);
		task1Clone.setSource(null);
		task2Clone.setSource(null);
		return StreamUtils.elementEquals(mapper, task1Clone, task2Clone);
	
	}
}
