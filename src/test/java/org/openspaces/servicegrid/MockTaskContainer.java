package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;

public class MockTaskContainer {

	private final StreamProducer<TaskExecutorState> stateWriter;
	private final Object taskExecutor;
	private final URL executorId;
	private final StreamConsumer<Task> taskConsumer;
	private URL lastTaskId;
	
	public MockTaskContainer(URL executorId, StreamProducer<TaskExecutorState> stateWriter, StreamConsumer<Task> taskConsumer,Object taskExecutor) {
		this.executorId = executorId;
		this.stateWriter = stateWriter;
		this.taskConsumer = taskConsumer;
		this.taskExecutor = taskExecutor;
	}

	private void afterExecute(URL taskId, Task task) {

		final TaskExecutorState state = getTaskExecutorState();
		state.completeExecutingTask(taskId);
		stateWriter.addElement(getExecutorId(), state);
	}

	private TaskExecutorState getTaskExecutorState() {
		if (taskExecutor instanceof TaskExecutor<?>) {
			return ((TaskExecutor<?>) taskExecutor).getState();
		}
		else if (taskExecutor instanceof ImpersonatingTaskExecutor<?>) {
			return ((ImpersonatingTaskExecutor<?>) taskExecutor).getState();
		}
		else {
			throw new IllegalStateException("taskExecutor illegal type");
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
		
		final TaskExecutorState state = getTaskExecutorState();
		Preconditions.checkNotNull(state);
		
		URL taskId;
		if (lastTaskId == null) {
			taskId = taskConsumer.getFirstElementId(executorId);
		}
		else {
			taskId = taskConsumer.getNextElementId(lastTaskId);
		}
		
		if (taskId != null) {
			final Task task = taskConsumer.getElement(taskId);
			state.executeTask(taskId);
			lastTaskId = taskId;
			beforeExecute(task);
			execute(task);
			afterExecute(taskId, task);
			needAnotherStep = true;
		}
		
		return needAnotherStep;
	}

	private void execute(final Task task) {
		if (task.getImpersonatedTarget() != null) {
			Preconditions.checkArgument(
					taskExecutor instanceof ImpersonatingTaskExecutor, 
					getExecutorId() + " cannot handle task, since it requires impersonation");
			final ImpersonatingTaskExecutor<?> impersonatingTaskExecutor = (ImpersonatingTaskExecutor<?>) taskExecutor;
			final TaskExecutorStateModifier impersonatedStateModifier = new TaskExecutorStateModifier() {
				
				@Override
				public void updateState(final ServiceInstanceState impersonatedState) {
					stateWriter.addElement(task.getImpersonatedTarget(), impersonatedState);							
				}

			};
			impersonatingTaskExecutor.execute(task, impersonatedStateModifier);
		}
		else {
			((TaskExecutor<?>) taskExecutor).execute(task);
		}
	}
	
	public URL getExecutorId() {
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
	
	
}