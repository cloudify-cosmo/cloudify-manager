package org.openspaces.servicegrid.mock;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URI;
import java.util.Map;
import java.util.Set;

import junit.framework.Assert;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.TaskProducerTask;
import org.openspaces.servicegrid.service.ServiceUtils;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamWriter;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.beust.jcommander.internal.Sets;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Maps;

public class MockTaskContainer {

	private final StreamWriter<TaskConsumerState> stateWriter;
	private final Object taskConsumer;
	private final URI taskConsumerId;
	private final StreamReader<Task> taskReader;
	private final StreamWriter<Task> taskWriter;
	private final StreamWriter<Task> persistentTaskWriter;
	private final StreamReader<TaskConsumerState> stateReader;
	private final Method taskConsumerStateHolderMethod;
	private final Map<Class<? extends ImpersonatingTask>,Method> impersonatedTaskConsumerMethodByType;
	private final Map<Class<? extends Task>,Method> taskConsumerMethodByType;
	private final Set<Method> taskConsumersToPersist;
	private final Method taskProducerMethod;
	private final CurrentTimeProvider timeProvider;

	// state objects that mocks process termination 
	private boolean killed;
	
	
	public MockTaskContainer(MockTaskContainerParameter parameterObject) {
		this.taskConsumerId = parameterObject.getExecutorId();
		this.stateReader = parameterObject.getStateReader();
		this.stateWriter = parameterObject.getStateWriter();
		this.taskReader = parameterObject.getTaskReader();
		this.taskWriter = parameterObject.getTaskWriter();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.killed = false;
		this.timeProvider = parameterObject.getTimeProvider();
		this.taskConsumerMethodByType = Maps.newHashMap();
		this.impersonatedTaskConsumerMethodByType = Maps.newHashMap();
		this.taskConsumersToPersist = Sets.newHashSet();
		this.persistentTaskWriter = parameterObject.getPersistentTaskWriter();
		
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
					Preconditions.checkArgument(TaskExecutorStateModifier.class.equals(parameterTypes[1]),"method second parameter type must be " + TaskExecutorStateModifier.class);
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
		StreamReader<Task> persistentTaskReader = parameterObject.getPersistentTaskReader();
		for (URI recoveredTaskId = persistentTaskReader.getFirstElementId(taskConsumerId);
			 recoveredTaskId != null;
			 recoveredTaskId = persistentTaskReader.getNextElementId(recoveredTaskId)) {
			
			Task task = persistentTaskReader.getElement(recoveredTaskId, Task.class);
			Preconditions.checkNotNull(task);
			ServiceUtils.addTask(taskWriter, taskConsumerId, task);
		}
	}

	private void afterExecute(URI taskId, Task task) {

		final TaskConsumerState state = getTaskConsumerState();
		state.completeExecutingTask(taskId);
		stateWriter.addElement(getTaskConsumerId(), state);
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
		Preconditions.checkNotNull(task.getTarget());
		Preconditions.checkArgument(
				task.getTarget().equals(getTaskConsumerId()),
				"Expected task target is %s instead found %s", getTaskConsumerId() , task.getTarget());
		
		final TaskConsumerState state = getTaskConsumerState();
		Preconditions.checkState(state.getCompletedTasks().size() < 1000, "%s completed task list is bigger than 1000, probably span out of control.", taskConsumer.getClass());
		stateWriter.addElement(getTaskConsumerId(), state);	
	}

	/**
	 * @return the processed task
	 */
	public Task consumeNextTask() {
		
		Task task = null;
		if (!killed) {
			
			URI taskId;
			TaskConsumerState state = getTaskConsumerState();
			try {
				taskId = ServiceUtils.getNextTaskId(state, taskReader, taskConsumerId);
			}
			catch (IndexOutOfBoundsException e) {
				// remote state had failover 
				state.getCompletedTasks().clear();
				Preconditions.checkState(state.getExecutingTasks().isEmpty());
				taskId = ServiceUtils.getNextTaskId(state, taskReader, taskConsumerId);
			}
			
			if (taskId != null) {
				task = taskReader.getElement(taskId, Task.class);
				state.executeTask(taskId);
				beforeExecute(task);
				execute(task);
				afterExecute(taskId, task);
			}
		}
		return task;
	}

	private void submitTasks(long nowTimestamp,
			Iterable<? extends Task> newTasks) {
		for (final Task newTask : newTasks) {
			newTask.setSource(taskConsumerId);
			newTask.setSourceTimestamp(nowTimestamp);
			ServiceUtils.addTask(taskWriter, newTask.getTarget(), newTask);
		}
	}

	private void execute(final Task task) {
		if (task instanceof TaskProducerTask) {
			Preconditions.checkArgument(
					taskProducerMethod != null, 
					"%s cannot consume task %s", taskConsumer.getClass(), task);
			
			TaskProducerTask taskProducerTask = (TaskProducerTask) task;
			long nowTimestamp = timeProvider.currentTimeMillis();
			for (int i = 0 ; i < taskProducerTask.getMaxNumberOfSteps(); i++) {
				final Iterable<? extends Task> newTasks = (Iterable<? extends Task>) invokeMethod(taskProducerMethod);
				if (Iterables.isEmpty(newTasks)) {
					break;
				}
				submitTasks(nowTimestamp, newTasks);
			}		
		}
		else if (!(task instanceof ImpersonatingTask)) {
			Method executorMethod = taskConsumerMethodByType.get(task.getClass());
			Preconditions.checkArgument(
					executorMethod != null, 
					"%s cannot consume task %s", taskConsumer.getClass(), task.getClass());
			invokeMethod(executorMethod, task);
			if (taskConsumersToPersist.contains(executorMethod)) {
				ServiceUtils.addTask(persistentTaskWriter, taskConsumerId, task);
			}
		} else {
			Method executorMethod = impersonatedTaskConsumerMethodByType.get(task.getClass());
			Preconditions.checkArgument(
					executorMethod != null, 
					"%s cannot consume impersonating task %s", taskConsumer.getClass(), task.getClass());
			final TaskExecutorStateModifier impersonatedStateModifier = new TaskExecutorStateModifier<TaskConsumerState>() {
				
				@Override
				public void updateState(final TaskConsumerState impersonatedState) {
					URI impersonatedTargetId = ((ImpersonatingTask)task).getImpersonatedTarget();
					Preconditions.checkNotNull(impersonatedTargetId);
					Assert.assertEquals(impersonatedTargetId.getHost(), "localhost");
					stateWriter.addElement(impersonatedTargetId, impersonatedState);
				}

				@Override
				public TaskConsumerState getState(Class<? extends TaskConsumerState> clazz) {
					URI impersonatedTargetId = ((ImpersonatingTask)task).getImpersonatedTarget();
					Preconditions.checkNotNull(impersonatedTargetId);
					Assert.assertEquals(impersonatedTargetId.getHost(), "localhost");
					URI lastElementId = stateReader.getLastElementId(impersonatedTargetId);
					if (lastElementId != null) {
						return stateReader.getElement(lastElementId, clazz);
					}
					return null;
				}
			};
			invokeMethod(executorMethod, task, impersonatedStateModifier);
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