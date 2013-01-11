package org.openspaces.servicegrid.mock;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URI;
import java.util.Map;

import junit.framework.Assert;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Maps;

public class MockTaskContainer {

	private final StreamProducer<TaskExecutorState> stateWriter;
	private final Object taskExecutor;
	private final URI executorId;
	private final StreamConsumer<Task> taskConsumer;
	private final StreamConsumer<TaskExecutorState> stateReader;
	private boolean killed;
	private final Method getStateMethod;
	private final Map<Class<? extends Task>,Method> impersonatedExecuteMethodByType;
	private final Map<Class<? extends Task>,Method> executeMethodByType;
	
	public MockTaskContainer(MockTaskContainerParameter parameterObject) {
		this.executorId = parameterObject.getExecutorId();
		this.stateReader = parameterObject.getStateReader();
		this.stateWriter = parameterObject.getStateWriter();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.taskExecutor = parameterObject.getTaskExecutor();
		this.killed = false;
		this.getStateMethod = getMethodByName("getState");
		
		this.executeMethodByType = Maps.newHashMap();
		this.impersonatedExecuteMethodByType = Maps.newHashMap();
		
		for (Method method : taskExecutor.getClass().getMethods()) {
			Class<?>[] parameterTypes = method.getParameterTypes();
			if (method.getAnnotation(TaskExecutor.class) != null) {
				Preconditions.checkArgument(parameterTypes.length >= 1 && !ImpersonatingTask.class.isAssignableFrom(parameterTypes[0]), "execute method parameter " + parameterTypes[0] + " is an impersonating task. Use " + ImpersonatingTask.class.getSimpleName() + " annotation instead, in " + taskExecutor.getClass());
				Preconditions.checkArgument(parameterTypes.length == 1, "task executor method must have one parameter");
				Preconditions.checkArgument(Task.class.isAssignableFrom(parameterTypes[0]), "execute method parameter " + parameterTypes[0] + " is not a task in " + taskExecutor.getClass());
				Class<? extends Task> taskType = (Class<? extends Task>) parameterTypes[0];
				executeMethodByType.put(taskType, method);
			}
			else if (method.getAnnotation(ImpersonatingTaskExecutor.class) != null) {
				Preconditions.checkArgument(parameterTypes.length == 2, "impersonating task executor method must have two parameters");
				Preconditions.checkArgument(ImpersonatingTask.class.isAssignableFrom(parameterTypes[0]), "execute method parameter " + parameterTypes[0] + " is not an impersonating task in " + taskExecutor);
				Class<? extends ImpersonatingTask> taskType = (Class<? extends ImpersonatingTask>) parameterTypes[0];
				Preconditions.checkArgument(TaskExecutorStateModifier.class.equals(parameterTypes[1]),"execute method second parameter type must be " + TaskExecutorStateModifier.class);
				impersonatedExecuteMethodByType.put(taskType, method);
			}
		}
	}

	private Method getMethodByName(String methodName, Class<?> ... parameterTypes) {
		Method method;
		try {
			method = taskExecutor.getClass().getMethod(methodName,parameterTypes);
		} catch (final NoSuchMethodException e) {
			return null;
		} catch (final SecurityException e) {
			throw Throwables.propagate(e);
		}
		return method;
	}

	private void afterExecute(URI taskId, Task task) {

		final TaskExecutorState state = getTaskExecutorState();
		state.completeExecutingTask(taskId);
		stateWriter.addElement(getExecutorId(), state);
	}

	private TaskExecutorState getTaskExecutorState() {
		return invokeMethod(getStateMethod);
	}

	private TaskExecutorState invokeMethod(Method method, Object ... args) {
		try {
			return (TaskExecutorState) method.invoke(taskExecutor, args);
		} catch (final IllegalAccessException e) {
			throw Throwables.propagate(e);
		} catch (final IllegalArgumentException e) {
			throw Throwables.propagate(e);
		} catch (final InvocationTargetException e) {
			throw Throwables.propagate(e);
		}
	}

	private void beforeExecute(Task task) {
		Preconditions.checkNotNull(task.getTarget());
		Preconditions.checkArgument(
				task.getTarget().equals(getExecutorId()),
				"Expected task target is %s instead found %s", getExecutorId() , task.getTarget());
		
		final TaskExecutorState state = getTaskExecutorState();
		stateWriter.addElement(getExecutorId(), state);
	}

	/**
	 * @return true - if need to be called again
	 */
	public boolean stepTaskExecutor() {
		
		boolean needAnotherStep = false;
		if (!killed) {
			
			URI taskId = getNextTaskId();
			
			if (taskId != null) {
				final Task task = taskConsumer.getElement(taskId, Task.class);
				getTaskExecutorState().executeTask(taskId);
				beforeExecute(task);
				execute(task);
				afterExecute(taskId, task);
			}
			
			URI nextTaskId = getNextTaskId();
			needAnotherStep = (nextTaskId != null);
		}
		return needAnotherStep;
	}

	private URI getNextTaskId() {
		return getNextTaskId(getTaskExecutorState());
	}

	private URI getNextTaskId(final TaskExecutorState state) {
		Preconditions.checkNotNull(state);
		final URI lastTaskId = getLastTaskIdOrNull(state);
		URI taskId;
		if (lastTaskId == null) {
			taskId = taskConsumer.getFirstElementId(executorId);
		}
		else {
			taskId = taskConsumer.getNextElementId(lastTaskId);
		}
		return taskId;
	}

	private URI getLastTaskIdOrNull(final TaskExecutorState state) {
		return Iterables.getLast(Iterables.concat(state.getCompletedTasks(),state.getExecutingTasks()), null);
	}

	private void execute(final Task task) {
		if (!(task instanceof ImpersonatingTask)) {
			Method executorMethod = executeMethodByType.get(task.getClass());
			Preconditions.checkArgument(
					executorMethod != null, 
					taskExecutor.getClass() + " cannot handle task " + task.getClass());
			invokeMethod(executorMethod, task);
		} else {
			Method executorMethod = impersonatedExecuteMethodByType.get(task.getClass());
			Preconditions.checkArgument(
					executorMethod != null, 
					taskExecutor.getClass() + " cannot handle impersonation task " + task.getClass());
			final TaskExecutorStateModifier impersonatedStateModifier = new TaskExecutorStateModifier() {
				
				@Override
				public void updateState(final TaskExecutorState impersonatedState) {
					URI impersonatedTargetId = ((ImpersonatingTask)task).getImpersonatedTarget();
					Preconditions.checkNotNull(impersonatedTargetId);
					Assert.assertEquals(impersonatedTargetId.getHost(), "localhost");
					stateWriter.addElement(impersonatedTargetId, impersonatedState);
				}

				@Override
				public TaskExecutorState getState() {
					URI impersonatedTargetId = ((ImpersonatingTask)task).getImpersonatedTarget();
					Preconditions.checkNotNull(impersonatedTargetId);
					Assert.assertEquals(impersonatedTargetId.getHost(), "localhost");
					URI lastElementId = stateReader.getLastElementId(impersonatedTargetId);
					if (lastElementId != null) {
						return stateReader.getElement(lastElementId, TaskExecutorState.class);
					}
					return null;
				}

			};
			invokeMethod(executorMethod, task, impersonatedStateModifier);
		}
	}
	
	public URI getExecutorId() {
		return executorId;
	}

	@Override
	public int hashCode() {
		final int prime = 31;
		int result = 1;
		result = prime * result
				+ ((executorId == null) ? 0 : executorId.hashCode());
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
		if (executorId == null) {
			if (other.executorId != null)
				return false;
		} else if (!executorId.equals(other.executorId))
			return false;
		return true;
	}
	
	@Override
	public String toString() {
		return taskExecutor.toString();
	}

	public void kill() {
		this.killed = true;
	}
}