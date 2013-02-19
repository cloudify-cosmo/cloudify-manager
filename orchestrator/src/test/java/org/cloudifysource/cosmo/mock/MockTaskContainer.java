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

import com.beust.jcommander.internal.Lists;
import com.beust.jcommander.internal.Sets;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.*;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.state.*;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class MockTaskContainer {

	private final Object taskConsumer;
	private final URI taskConsumerId;
	private Class<? extends TaskConsumerState> taskConsumerStateClass;
	private final TaskReader taskReader;
	private final TaskWriter taskWriter;
	private final TaskWriter persistentTaskWriter;
	private final Method taskConsumerStateHolderMethod;
	private final StateReader stateReader;
	private final StateWriter stateWriter;
	private final Map<Class<? extends Task>,Method> impersonatedTaskConsumerMethodByType;
	private final Map<Class<? extends Task>,Method> taskConsumerMethodByType;
	private final Set<Class<? extends Task>> tasksToPersist;
	private final Set<Class<? extends Task>> tasksToAddHistory;
	private final Method taskProducerMethod;
	private final CurrentTimeProvider timeProvider;
	private final TaskConsumerHistoryModifier taskConsumerHistoryModifier;

	// state objects that mocks process termination 
	private boolean killed;
	
	private TaskConsumerStateModifier<TaskConsumerState> stateModifier;
	private Map<URI, MockTaskConsumerHistoryModifier> historyModifiers;

	
	public MockTaskContainer(MockTaskContainerParameter parameterObject) {
		this.taskConsumerId = parameterObject.getExecutorId();
		this.stateWriter = parameterObject.getStateWriter();
		this.stateReader = parameterObject.getStateReader();
		this.taskReader = parameterObject.getTaskReader();
		this.taskWriter = parameterObject.getTaskWriter();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.killed = false;
		this.timeProvider = parameterObject.getTimeProvider();
		this.taskConsumerMethodByType = Maps.newHashMap();
		this.impersonatedTaskConsumerMethodByType = Maps.newHashMap();
		this.tasksToPersist = Sets.newHashSet();
		this.tasksToAddHistory = Sets.newHashSet();
		this.persistentTaskWriter = parameterObject.getPersistentTaskWriter();
		this.historyModifiers = Maps.newLinkedHashMap();
		
		//Reflect on @TaskProducer and @TaskConsumer methods
		Method taskProducerMethod = null;
		Method taskConsumerStateHolderMethod = null;
		taskConsumerHistoryModifier = newTaskConsumerHistoryModifier(taskConsumerId);
		for (Method method : taskConsumer.getClass().getMethods()) {
			Class<?>[] parameterTypes = method.getParameterTypes();
			TaskConsumer taskConsumerAnnotation = method.getAnnotation(TaskConsumer.class);
			ImpersonatingTaskConsumer impersonatingTaskConsumerAnnotation = method.getAnnotation(ImpersonatingTaskConsumer.class);
			TaskProducer taskProducerAnnotation = method.getAnnotation(TaskProducer.class);
			TaskConsumerStateHolder taskConsumerStateHolderAnnotation = method.getAnnotation(TaskConsumerStateHolder.class);
			if (taskConsumerAnnotation != null) {
				Preconditions.checkArgument(method.getReturnType().equals(Void.TYPE), method + " return type must be void");
				Preconditions.checkArgument(parameterTypes.length == 1, "method must have one parameter");
				Preconditions.checkArgument(Task.class.isAssignableFrom(parameterTypes[0]), "method parameter " + parameterTypes[0] + " is not a task in " + taskConsumer.getClass());
				Class<? extends Task> taskType = (Class<? extends Task>) parameterTypes[0];
				taskConsumerMethodByType.put(taskType, method);
				
				if (taskConsumerAnnotation.persistTask()) {
					tasksToPersist.add(taskType);
				}
				
				if (!taskConsumerAnnotation.noHistory()) {
					tasksToAddHistory.add(taskType);
				}
			
			} else if (impersonatingTaskConsumerAnnotation != null) {
					Preconditions.checkArgument(method.getReturnType().equals(Void.TYPE), method + " return type must be void");
					Preconditions.checkArgument(parameterTypes.length == 2, "Impersonating task executor method must have two parameters");
					Preconditions.checkArgument(Task.class.isAssignableFrom(parameterTypes[0]), "method first parameter %s is not an impersonating task in %s",parameterTypes[0], taskConsumer.getClass());
					Class<? extends Task> taskType = (Class<? extends Task>) parameterTypes[0];
					Preconditions.checkArgument(TaskConsumerStateModifier.class.equals(parameterTypes[1]),"method second parameter type must be " + TaskConsumerStateModifier.class);
					impersonatedTaskConsumerMethodByType.put(taskType, method);
					
					if (!impersonatingTaskConsumerAnnotation.noHistory()) {
						tasksToAddHistory.add(taskType);
					}

			} else if (taskProducerAnnotation != null) {
					Preconditions.checkArgument(Iterable.class.equals(method.getReturnType()), "%s return type must be Iterable<Task>",method);
					Preconditions.checkArgument(parameterTypes.length == 0, "%s method must not have any parameters", method);				
					Preconditions.checkArgument(taskProducerMethod == null, "%s can have at most one @" + TaskProducer.class.getSimpleName()+" method", taskConsumer.getClass());
					taskProducerMethod = method;
					
			} else if (taskConsumerStateHolderAnnotation != null) {
				taskConsumerStateHolderMethod = method;
				final TaskConsumerState state = (TaskConsumerState) invokeMethod(taskConsumerStateHolderMethod);
				taskConsumerStateClass = state.getClass();
			}
		}
		this.taskProducerMethod = taskProducerMethod;
		this.taskConsumerStateHolderMethod = taskConsumerStateHolderMethod;
		this.stateModifier = newStateModifier();
		//recover persisted tasks
		recoverPersistedTasks(parameterObject.getPersistentTaskReader());
	}

	private TaskConsumerHistoryModifier newTaskConsumerHistoryModifier(URI stateId) {
		final URI historyId = ServiceUtils.toTasksHistoryId(stateId);
		MockTaskConsumerHistoryModifier historyModifier = historyModifiers.get(historyId);
		if (historyModifier == null) {
			historyModifier = new MockTaskConsumerHistoryModifier(historyId);
			historyModifiers.put(stateId, historyModifier);
		}
		return historyModifier;
	}

	private void recoverPersistedTasks(TaskReader persistentTaskReader) {
		
		while(true) {
			final Task task = persistentTaskReader.removeNextTask(taskConsumerId);
			if (task == null) {
				break;
			}
			Preconditions.checkState(task.getConsumerId().equals(taskConsumerId)); 
			taskWriter.postNewTask(task);
		}
	}

	private void afterTaskExecute(Task task) {

		final TaskConsumerState state = getTaskConsumerState();
		state.setExecutingTask(null);
		stateModifier.put(state);
		
		taskConsumerHistoryModifier.addTaskToHistory(task);
	}

	private void afterImpersonatingTask(Task task, TaskConsumerStateModifier<TaskConsumerState> stateModifier, TaskConsumerHistoryModifier historyModifier) {
		final TaskConsumerState state = stateModifier.get();
		Preconditions.checkNotNull(state);
		state.setExecutingTask(null);
		historyModifier.addTaskToHistory(task);
		stateModifier.put(state);
	}
	
	private TaskConsumerState getTaskConsumerState() {
		Preconditions.checkState(taskConsumerStateHolderMethod != null, taskConsumer.getClass() + " does not have any method annotated with @" + TaskConsumerStateHolder.class.getSimpleName());
		return (TaskConsumerState) invokeMethod(taskConsumerStateHolderMethod);
	}

	private Object invokeMethod(Method method, Object ... args) {
		try {
			return method.invoke(taskConsumer, args);
		} catch (final IllegalAccessException e) {
			throw Throwables.propagate(e);
		} catch (final IllegalArgumentException e) {
			throw Throwables.propagate(e);
		} catch (final InvocationTargetException e) {
			throw Throwables.propagate(e.getCause());
		}
	}

	private void beforeExecute(Task task) {
		Preconditions.checkNotNull(task.getConsumerId());
		Preconditions.checkArgument(
				task.getConsumerId().equals(getTaskConsumerId()),
				"Expected task target is %s instead found %s", getTaskConsumerId() , task.getConsumerId());
		
		TaskConsumerState state = stateModifier.get();
		if (state == null) {
			state = getTaskConsumerState();
		}
		Preconditions.checkState(state.getExecutingTask() == null, "Task Consumer cannot consume more than one task at a time. Currently executing "+ state.getExecutingTask());
		state.setExecutingTask(task);
		
		stateModifier.put(state);	
	}
	
	private void beforeExecute(Task task, TaskConsumerStateModifier<TaskConsumerState> stateModifier) {
		Preconditions.checkNotNull(task.getConsumerId());
		Preconditions.checkArgument(
				task.getConsumerId().equals(getTaskConsumerId()),
				"Expected task target is %s instead found %s", getTaskConsumerId() , task.getConsumerId());
		
		final TaskConsumerState state = stateModifier.get();
		if (state != null) {
			Preconditions.checkState(state.getExecutingTask() == null, "Task Consumer cannot consume more than one task at a time. Currently executing "+ state.getExecutingTask());
			state.setExecutingTask(task);
			stateModifier.put(state);
		}
	}

	/**
	 * @return the processed task
	 */
	public Task consumeNextTask() {
		
		Task task = null;
		if (!killed) {
			
			task = taskReader.removeNextTask(taskConsumerId);
			if (task != null) {
				execute(task);
			}
		}
		return task;
	}

	
	private Iterable<Task> submitTasks(
			final long nowTimestamp,
			final Iterable<? extends Task> newTasks) {
		
		List<Task> submitted = Lists.newArrayList();
		
		for (final Task newTask : newTasks) {
			newTask.setProducerId(taskConsumerId);
			newTask.setProducerTimestamp(nowTimestamp);
			if (taskWriter.postNewTask(newTask)) {
				submitted.add(newTask);
			}
		}
		
		return submitted;
	}

	private void execute(final Task task) {
		Preconditions.checkNotNull(task);
		if (task instanceof TaskProducerTask) {
			executeTaskProducerTask(task);
		}
		else if (!task.getStateId().equals(this.taskConsumerId)) {
			executeImpersonatingTask(task);
		} else {
			executeTask(task);
		}
	}

	private void executeTaskProducerTask(final Task task) {
		beforeExecute(task);
		try {
			produceTasks((TaskProducerTask)task);		
		}
		finally {
			afterTaskExecute(task);
		}
	}

	private void executeTask(final Task task) {
		Preconditions.checkArgument(taskConsumerStateClass.equals(task.getStateClass()), 
				"Task %s has the wrong stateClass. Expected:%s  Actual:%s",
				task.getClass(), taskConsumerStateClass, task.getStateClass());
		
		beforeExecute(task);
		try {
			consumeTask(task);
		}
		finally {
			afterTaskExecute(task);
		}
	}

	private void executeImpersonatingTask(final Task task) {
		final TaskConsumerStateModifier<TaskConsumerState> impersonatingStateModifier = newImpersonatingStateModifier(task.getStateId(), task.getStateClass());
		final TaskConsumerHistoryModifier impersonatingHistoryModifier = newTaskConsumerHistoryModifier(task.getStateId());
		beforeExecute(task, impersonatingStateModifier);
		try {
			consumeImpersonatingTask(task, impersonatingStateModifier);
		}
		finally {
			afterImpersonatingTask(task, impersonatingStateModifier, impersonatingHistoryModifier);
		}
	}

	private void consumeImpersonatingTask(final Task task, final TaskConsumerStateModifier<?> impersonatedStateModifier) {
		final Method executorMethod = impersonatedTaskConsumerMethodByType.get(task.getClass());
		Preconditions.checkArgument(
				executorMethod != null, 
				"%s cannot consume impersonating task %s", taskConsumer.getClass(), task.getClass());
		invokeMethod(executorMethod, task, impersonatedStateModifier);
	}

	private TaskConsumerStateModifier<TaskConsumerState> newImpersonatingStateModifier(
			final URI stateId, final Class<? extends TaskConsumerState> stateClass) {
		
		Preconditions.checkNotNull(stateId);
		Preconditions.checkNotNull(stateClass);
		
		final TaskConsumerStateModifier<TaskConsumerState> impersonatedStateModifier = new TaskConsumerStateModifier<TaskConsumerState>() {
			
			Etag lastEtag = null;
			TaskConsumerState impersonatedState;
			
			@Override
			public void put(final TaskConsumerState newImpersonatedState) {
				Preconditions.checkNotNull(stateId);
				Preconditions.checkNotNull(lastEtag);
				lastEtag = stateWriter.put(stateId, newImpersonatedState, lastEtag);
				impersonatedState = newImpersonatedState;
			}

			@Override
			public TaskConsumerState get() {
				if (lastEtag == null) {
					
					EtagState<TaskConsumerState> etagState = stateReader.get(stateId, stateClass);
					if (etagState == null) {
						lastEtag = Etag.EMPTY;
						impersonatedState = null;
					}
					else {
						lastEtag = etagState.getEtag();
						impersonatedState = etagState.getState();
					}
				}
				else {
					// do not go to remote storage, since we must make sure that for the lifetime
					// of this object, there isn't anyone else writing to the remote storage
					// by handling the lastEtag ourselves - we ensure we are the only ones writing to the storage
					//this is so we make sure we are the only ones writing to the state right now - no conflicts at all.
				}
				return impersonatedState;
			}
		};
		return impersonatedStateModifier;
	}
	
	private TaskConsumerStateModifier<TaskConsumerState> newStateModifier() {
		final TaskConsumerStateModifier<TaskConsumerState> stateModifier = new TaskConsumerStateModifier<TaskConsumerState>() {
			
			Etag lastEtag = null;
			TaskConsumerState state = null;

			@Override
			public void put(final TaskConsumerState newState) {
				Preconditions.checkNotNull(lastEtag);
				try {
					lastEtag = stateWriter.put(taskConsumerId, newState, lastEtag);
					state = newState;
				}
				catch (EtagPreconditionNotMetException e) {
					//wrong etag
					if (!Etag.EMPTY.equals(e.getResponseEtag())) {
						throw e;
					}
				
					//remote server suffered a restart, need to update it with last state
					lastEtag = stateWriter.put(taskConsumerId, newState, Etag.EMPTY);
					state = newState;
				}
			}

			@Override
			public TaskConsumerState get() {
				if (lastEtag == null) {
					EtagState<TaskConsumerState> etagState = stateReader.get(taskConsumerId, taskConsumerStateClass);
					if (etagState == null) {
						lastEtag = Etag.EMPTY;
						state = null;
					}
					else {
						lastEtag = etagState.getEtag();
						state = etagState.getState();
					}
				}
				return state;
			}
		};
		return stateModifier;
	}
	
	private void consumeTask(final Task task) {
		Method executorMethod = taskConsumerMethodByType.get(task.getClass());
		Preconditions.checkArgument(
				executorMethod != null, 
				"%s cannot consume task %s", taskConsumer.getClass(), task.getClass());
		invokeMethod(executorMethod, task);
		if (tasksToPersist.contains(task.getClass())) {
			persistentTaskWriter.postNewTask(task);
		}
	}

	private void produceTasks(final TaskProducerTask taskProducerTask) {
		Preconditions.checkArgument(
				taskProducerMethod != null, 
				"%s cannot consume task %s", taskConsumer.getClass(), taskProducerTask);
		
		final long nowTimestamp = timeProvider.currentTimeMillis();
		for (int i = 0 ; i < taskProducerTask.getMaxNumberOfSteps(); i++) {
			final Iterable<? extends Task> newTasks = (Iterable<? extends Task>) invokeMethod(taskProducerMethod);
			Iterable<Task> submitted = submitTasks(nowTimestamp, newTasks);
			if (Iterables.isEmpty(submitted)) {
				break;
			}			
		}
	}
	
	public URI getTaskConsumerId() {
		return taskConsumerId;
	}

	@Override
	public int hashCode() {
		final int prime = 31;
		int result = 1;
		result = prime * result
				+ ((taskConsumerId == null) ? 0 : taskConsumerId.hashCode());
		return result;
	}

	@Override
	public boolean equals(Object obj) {
		if (this == obj)
			return true;
		if (obj == null)
			return false;
		if (getClass() != obj.getClass())
			return false;
		MockTaskContainer other = (MockTaskContainer) obj;
		if (taskConsumerId == null) {
			if (other.taskConsumerId != null)
				return false;
		} else if (!taskConsumerId.equals(other.taskConsumerId))
			return false;
		return true;
	}
	
	@Override
	public String toString() {
		return taskConsumer.toString();
	}

	public void killMachine() {
		Preconditions.checkState(!killed);
		this.killed = true;
	}

	public Object getTaskConsumer() {
		return taskConsumer;
	}
	
	public class MockTaskConsumerHistoryModifier implements TaskConsumerHistoryModifier {
				
		private final URI historyId;
		private TaskConsumerHistory history;
		private Etag lastEtag;
		
		public MockTaskConsumerHistoryModifier(final URI historyId) {
			this.historyId = historyId;
		}
		
		@Override
		public void addTaskToHistory(Task task) {
			if (history == null) {
				init(historyId);
			}
			if (tasksToAddHistory.contains(task.getClass())) {
				history.getTasksHistory().add(task);
			}
			try {
				lastEtag = stateWriter.put(historyId, history, lastEtag);
			} catch (EtagPreconditionNotMetException e) {
				//wrong etag
				if (!Etag.EMPTY.equals(e.getResponseEtag())) {
					throw e;
				}
				// management had a failover which caused a severe memory loss
				// upload all histories related to this task consumer
				for (MockTaskConsumerHistoryModifier historyModifier: historyModifiers.values()) {
					historyModifier.onManagementFailure();
				}
			}
		}
		
		private void init(final URI historyId) {
			final EtagState<TaskConsumerHistory> etagState = stateReader.get(historyId, TaskConsumerHistory.class);
			if (etagState == null) {
				history = new TaskConsumerHistory();
				lastEtag = Etag.EMPTY;
			}
			else {
				history = etagState.getState();
				lastEtag = etagState.getEtag();
			}
		}
		
		private void onManagementFailure() {
			//remote server suffered a restart, need to update it with last state
			lastEtag = stateWriter.put(historyId, history, Etag.EMPTY);
		}
	}
	
}
