package org.openspaces.servicegrid.mock;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URI;
import java.util.Map;
import java.util.Set;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskConsumerStateModifier;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.TaskProducerTask;
import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.TaskWriter;
import org.openspaces.servicegrid.state.Etag;
import org.openspaces.servicegrid.state.EtagState;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.beust.jcommander.internal.Sets;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Maps;

public class MockTaskContainer {

	private final Object taskConsumer;
	private final URI taskConsumerId;
	private final TaskReader taskReader;
	private final TaskWriter taskWriter;
	private final TaskWriter persistentTaskWriter;
	private final Method taskConsumerStateHolderMethod;
	private final StateReader stateReader;
	private final StateWriter stateWriter;
	private final Map<Class<? extends ImpersonatingTask>,Method> impersonatedTaskConsumerMethodByType;
	private final Map<Class<? extends Task>,Method> taskConsumerMethodByType;
	private final Set<Method> taskConsumersToPersist;
	private final Method taskProducerMethod;
	private final CurrentTimeProvider timeProvider;

	// state objects that mocks process termination 
	private boolean killed;
	
	// last task is used to detect inconsistencies in management machine providing tasks
	private Task lastTask;
	private ObjectMapper mapper;
	private TaskConsumerStateModifier<TaskConsumerState> stateModifier;

	
	public MockTaskContainer(MockTaskContainerParameter parameterObject) {
		this.taskConsumerId = parameterObject.getExecutorId();
		this.stateModifier = newStateModifier(parameterObject.getStateReader(), parameterObject.getStateWriter(), taskConsumerId);
		this.stateWriter = parameterObject.getStateWriter();
		this.stateReader = parameterObject.getStateReader();
		this.taskReader = parameterObject.getTaskReader();
		this.taskWriter = parameterObject.getTaskWriter();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.killed = false;
		this.timeProvider = parameterObject.getTimeProvider();
		this.taskConsumerMethodByType = Maps.newHashMap();
		this.impersonatedTaskConsumerMethodByType = Maps.newHashMap();
		this.taskConsumersToPersist = Sets.newHashSet();
		this.persistentTaskWriter = parameterObject.getPersistentTaskWriter();
		this.mapper = StreamUtils.newObjectMapper();
		//Reflect on @TaskProducer and @TaskConsumer methods
		Method taskProducerMethod = null;
		Method taskConsumerStateHolderMethod = null;

		for (Method method : taskConsumer.getClass().getMethods()) {
			Class<?>[] parameterTypes = method.getParameterTypes();
			TaskConsumer taskConsumerAnnotation = method.getAnnotation(TaskConsumer.class);
			ImpersonatingTaskConsumer impersonatingTaskConsumerAnnotation = method.getAnnotation(ImpersonatingTaskConsumer.class);
			TaskProducer taskProducerAnnotation = method.getAnnotation(TaskProducer.class);
			TaskConsumerStateHolder taskConsumerStateHolderAnnotation = method.getAnnotation(TaskConsumerStateHolder.class);
			if (taskConsumerAnnotation != null) {
				Preconditions.checkArgument(method.getReturnType().equals(Void.TYPE), method + " return type must be void");
				Preconditions.checkArgument(parameterTypes.length >= 1 && !ImpersonatingTask.class.isAssignableFrom(parameterTypes[0]), "execute method parameter " + parameterTypes[0] + " is an impersonating task. Use " + ImpersonatingTask.class.getSimpleName() + " annotation instead, in " + taskConsumer.getClass());
				Preconditions.checkArgument(parameterTypes.length == 1, "method must have one parameter");
				Preconditions.checkArgument(Task.class.isAssignableFrom(parameterTypes[0]), "method parameter " + parameterTypes[0] + " is not a task in " + taskConsumer.getClass());
				Class<? extends Task> taskType = (Class<? extends Task>) parameterTypes[0];
				taskConsumerMethodByType.put(taskType, method);
				
				if (taskConsumerAnnotation.persistTask()) {
					taskConsumersToPersist.add(method);
				}
			
			} else if (impersonatingTaskConsumerAnnotation != null) {
					Preconditions.checkArgument(method.getReturnType().equals(Void.TYPE), method + " return type must be void");
					Preconditions.checkArgument(parameterTypes.length == 2, "Impersonating task executor method must have two parameters");
					Preconditions.checkArgument(ImpersonatingTask.class.isAssignableFrom(parameterTypes[0]), "method first parameter %s is not an impersonating task in %s",parameterTypes[0], taskConsumer.getClass());
					Class<? extends ImpersonatingTask> taskType = (Class<? extends ImpersonatingTask>) parameterTypes[0];
					Preconditions.checkArgument(TaskConsumerStateModifier.class.equals(parameterTypes[1]),"method second parameter type must be " + TaskConsumerStateModifier.class);
					impersonatedTaskConsumerMethodByType.put(taskType, method);

			} else if (taskProducerAnnotation != null) {
					Preconditions.checkArgument(Iterable.class.equals(method.getReturnType()), "%s return type must be Iterable<Task>",method);
					Preconditions.checkArgument(parameterTypes.length == 0, "%s method must not have any parameters", method);				
					Preconditions.checkArgument(taskProducerMethod == null, "%s can have at most one @" + TaskProducer.class.getSimpleName()+" method", taskConsumer.getClass());
					taskProducerMethod = method;
					
			} else if (taskConsumerStateHolderAnnotation != null) {
				taskConsumerStateHolderMethod = method;
				final TaskConsumerState state = (TaskConsumerState) invokeMethod(taskConsumerStateHolderMethod);
			}
		}
		this.taskProducerMethod = taskProducerMethod;
		this.taskConsumerStateHolderMethod = taskConsumerStateHolderMethod;
		
		//recover persisted tasks
		recoverPersistedTasks(parameterObject.getPersistentTaskReader());
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

	private void afterTaskExecute(Task task, TaskConsumerState prevState) {

		final TaskConsumerState state = getTaskConsumerState();
		state.setExecutingTask(null);
		if (!StreamUtils.elementEquals(mapper, prevState, state)) {
			state.addTaskHistory(task);
		}
		stateModifier.put(state);
	}

	private void afterImpersonatingTask(ImpersonatingTask task, TaskConsumerState prevState, TaskConsumerStateModifier<TaskConsumerState> stateModifier) {
		final TaskConsumerState state = stateModifier.get(TaskConsumerState.class);
		state.setExecutingTask(null);
		if (!StreamUtils.elementEquals(mapper, prevState, state)) {
			state.addTaskHistory(task);
		}
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
		
		TaskConsumerState state = stateModifier.get(TaskConsumerState.class);
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
		
		final TaskConsumerState state = stateModifier.get(TaskConsumerState.class);
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

	
	private void submitTasks(
			final long nowTimestamp,
			final Iterable<? extends Task> newTasks) {
		for (final Task newTask : newTasks) {
			newTask.setSource(taskConsumerId);
			newTask.setProducerTimestamp(nowTimestamp);
			taskWriter.postNewTask(newTask);
		}
	}

	private void execute(final Task task) {
		Preconditions.checkNotNull(task);
		if (task instanceof TaskProducerTask) {
			executeTaskProducerTask(task);
		}
		else if (task instanceof ImpersonatingTask) {
			executeImpersonatingTask((ImpersonatingTask)task);
		} else {
			executeTask(task);
		}
	}

	private void executeTaskProducerTask(final Task task) {
		final TaskConsumerState prevState = StreamUtils.cloneElement(mapper, getTaskConsumerState());
		beforeExecute(task);
		try {
			produceTasks((TaskProducerTask)task);		
		}
		finally {
			afterTaskExecute(task, prevState);
		}
	}

	private void executeTask(final Task task) {
		final TaskConsumerState prevState = StreamUtils.cloneElement(mapper, getTaskConsumerState());
		beforeExecute(task);
		try {
			consumeTask(task);
		}
		finally {
			afterTaskExecute(task, prevState);
		}
	}

	private void executeImpersonatingTask(final ImpersonatingTask task) {
		final TaskConsumerStateModifier<TaskConsumerState> impersonatingStateModifier = newImpersonatingStateModifier(task);
		final TaskConsumerState state = impersonatingStateModifier.get(TaskConsumerState.class);
		final TaskConsumerState prevState = state == null ? null : StreamUtils.cloneElement(mapper, state);
		beforeExecute(task, impersonatingStateModifier);
		try {
			consumeImpersonatingTask(task, impersonatingStateModifier);
		}
		finally {
			afterImpersonatingTask(task, prevState, impersonatingStateModifier);
		}
	}

	private void consumeImpersonatingTask(final ImpersonatingTask task, final TaskConsumerStateModifier<?> impersonatedStateModifier) {
		final Method executorMethod = impersonatedTaskConsumerMethodByType.get(task.getClass());
		Preconditions.checkArgument(
				executorMethod != null, 
				"%s cannot consume impersonating task %s", taskConsumer.getClass(), task.getClass());
		invokeMethod(executorMethod, task, impersonatedStateModifier);
	}

	private TaskConsumerStateModifier<TaskConsumerState> newImpersonatingStateModifier(
			final ImpersonatingTask task) {
		final TaskConsumerStateModifier<TaskConsumerState> impersonatedStateModifier = new TaskConsumerStateModifier<TaskConsumerState>() {
			
			Etag lastEtag = Etag.EMPTY;
			
			@Override
			public void put(final TaskConsumerState impersonatedState) {
				final URI impersonatedTargetId = task.getStateId();
				Preconditions.checkNotNull(impersonatedTargetId);
				lastEtag = stateWriter.put(impersonatedTargetId, impersonatedState, lastEtag);
			}

			@Override
			public TaskConsumerState get(final Class<? extends TaskConsumerState> clazz) {
				final URI impersonatedTargetId = task.getStateId();
				Preconditions.checkNotNull(impersonatedTargetId);
				EtagState<TaskConsumerState> etagState = stateReader.get(impersonatedTargetId, clazz);
				if (etagState == null) {
					lastEtag = Etag.EMPTY;
					return null;
				}
				lastEtag = etagState.getEtag();
				return etagState.getState();
			}
		};
		return impersonatedStateModifier;
	}
	
	private static TaskConsumerStateModifier<TaskConsumerState> newStateModifier(final StateReader stateReader,final StateWriter stateWriter, final URI taskConsumerId) {
		final TaskConsumerStateModifier<TaskConsumerState> stateModifier = new TaskConsumerStateModifier<TaskConsumerState>() {
			
			Etag lastEtag = Etag.EMPTY;
			
			@Override
			public void put(final TaskConsumerState state) {
				lastEtag = stateWriter.put(taskConsumerId, state, lastEtag);
			}

			@Override
			public TaskConsumerState get(final Class<? extends TaskConsumerState> clazz) {
				EtagState<TaskConsumerState> etagState = stateReader.get(taskConsumerId, clazz);
				if (etagState == null) {
					lastEtag = Etag.EMPTY;
					return null;
				}
				lastEtag = etagState.getEtag();
				return etagState.getState();
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
		if (taskConsumersToPersist.contains(executorMethod)) {
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
			if (Iterables.isEmpty(newTasks)) {
				break;
			}
			submitTasks(nowTimestamp, newTasks);
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
	
}