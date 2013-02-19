/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
package org.cloudifysource.cosmo.mock;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.base.Joiner;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.LinkedListMultimap;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskProducerTask;
import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.TaskWriter;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.util.List;

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
	public boolean postNewTask(final Task task) {
		Preconditions.checkNotNull(task);
		Preconditions.checkNotNull(task.getConsumerId());
		Preconditions.checkNotNull(task.getProducerId());
		task.setConsumerId(StreamUtils.fixSlash(task.getConsumerId()));
		task.setProducerId(StreamUtils.fixSlash(task.getProducerId()));
		if (task.getStateId() != null) {
			task.setStateId(StreamUtils.fixSlash(task.getStateId()));
		}
		
		
		if (task.getStateId() == null) {
			task.setStateId(task.getConsumerId());
		}
		
		final URI key = task.getConsumerId();
		
		boolean foundDuplicate = containsTaskIgnoreProducerTimestamp(key, task);
		
		
		if (!foundDuplicate) {
			final String value = StreamUtils.toJson(mapper,task);
			streamById.put(key, value);
		}
		
		if (isLoggingEnabled() && logger.isInfoEnabled() && !(task instanceof TaskProducerTask)) {
			String request = "POST http://services/tasks/_new_task HTTP 1.1\n"+StreamUtils.toJson(mapper,task);
			String response = "HTTP/1.1 " + (foundDuplicate ? "409 Duplicate\nX-Status-Reason: Similar task already in queue": "200 OK")+"\n";
			logger.info(request +"\n"+ response+"\n");
		}
		return !foundDuplicate;
	
	}

	private boolean containsTaskIgnoreProducerTimestamp(final URI key,final Task task) {
		
		final String taskJson = StreamUtils.toJson(mapper, task);
		final String taskJsonErased = eraseProducerTimestamp(taskJson);
		
		return Iterables.tryFind(streamById.get(key), new Predicate<String>(){

			@Override
			public boolean apply(String otherTaskJson) {
				String otherTaskJsonErased = eraseProducerTimestamp(otherTaskJson);
				return StreamUtils.elementEquals(mapper, taskJsonErased, otherTaskJsonErased);
			}}).isPresent();
	}

	private String eraseProducerTimestamp(String taskJson) {
		Task taskClone = StreamUtils.fromJson(mapper,taskJson, Task.class);
		taskClone.setProducerTimestamp(null);
		return StreamUtils.toJson(mapper,taskClone);
	}

	@Override
	public <T extends Task> T removeNextTask(final URI taskConsumerId) {
		final URI key = StreamUtils.fixSlash(taskConsumerId);
		final List<String> tasks = streamById.get(key);
		if (tasks.isEmpty()) {
			if (isLoggingEnabled() && logger.isInfoEnabled()) {
				String request = "POST http://service/tasks/_remove__oldest_task HTTP 1.1\n{\n\tconsumer_id : " +key +"\n}\n";
				String response = "HTTP/1.1 404 Not Found";
				logger.info(request +"\n"+ response+"\n");
			}
			return null;
		}
		
		final String removed = tasks.remove(0);
		final T task = (T) StreamUtils.fromJson(mapper, removed, Task.class);
		if (isLoggingEnabled() && logger.isInfoEnabled()) {
			String request = "POST http://service/_remove_task HTTP 1.1\n{\n\tconsumer_id : " +key +"\n}\n";
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
			String request = "GET http://service/tasks/_list_tasks HTTP 1.1\n{\n\tconsumer_id : " +key.getPath() +"\n}\n";
			Joiner joiner = Joiner.on(",\n");
			String response = "HTTP/1.1 200 OK\n[";
			if (!Iterables.isEmpty(jsonTasks)) {
				response += joiner.join(jsonTasks)+"\n";
			}
			response += "]";
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
		task1Clone.setProducerId(null);
		task2Clone.setProducerId(null);
		return StreamUtils.elementEquals(mapper, task1Clone, task2Clone);
	
	}
}
