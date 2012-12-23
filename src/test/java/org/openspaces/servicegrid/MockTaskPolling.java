package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.rest.executors.TaskExecutorStateWriter;
import org.openspaces.servicegrid.rest.tasks.StreamConsumer;

import com.google.common.base.Preconditions;

public class MockTaskPolling {

	private final TaskExecutorStateWriter stateWriter;
	private final TaskExecutor<?> taskExecutor;
	private final URL executorId;
	private final StreamConsumer taskConsumer;
	private URL lastTaskId;
	
	public MockTaskPolling(URL executorId, TaskExecutorStateWriter stateWriter, StreamConsumer taskConsumer, TaskExecutor<?> taskExecutor) {
		this.executorId = executorId;
		this.stateWriter = stateWriter;
		this.taskConsumer = taskConsumer;
		this.taskExecutor = taskExecutor;
	}

	private void afterExecute(URL taskId, Task task) {

		final TaskExecutorState state = taskExecutor.getState();
		state.completeExecutingTask(taskId);
		stateWriter.put(getExecutorId(), state, null);
		
		if (task.getImpersonatedTarget() != null) {
			Preconditions.checkArgument(
					taskExecutor instanceof ImpersonatingTaskExecutor, 
					getExecutorId() + " cannot handle task, since it requires impersonation");
			ImpersonatingTaskExecutor<?,?> impersonatingTaskExecutor = (ImpersonatingTaskExecutor<?,?>) taskExecutor;
			stateWriter.put(task.getImpersonatedTarget(), impersonatingTaskExecutor.getImpersonatedState(), null);	
		}
	}

	private void beforeExecute(Task task) {
		Preconditions.checkNotNull(task.getTarget());
		Preconditions.checkArgument(
				task.getTarget().equals(getExecutorId()),
				"Expected task target is %s instead found %s", getExecutorId() , task.getTarget());
		
		final TaskExecutorState state = taskExecutor.getState();
		stateWriter.put(getExecutorId(), state, null);
	}

	public TaskExecutor<? extends TaskExecutorState> getTaskExecutor() {
		return taskExecutor;
	}
	

	public void stepTaskExecutor() {
		
		final TaskExecutorState state = taskExecutor.getState();
		
		if (!state.isExecutingTask()) {
			URL taskId;
			if (lastTaskId == null) {
				taskId = taskConsumer.getFirstId(executorId);
			}
			else {
				taskId = taskConsumer.getNextId(lastTaskId);
			}
			if (taskId != null) {
				Task task = taskConsumer.getById(taskId);
				state.executeTask(taskId);
				lastTaskId = taskId;
				beforeExecute(task);
				taskExecutor.execute(task);
				afterExecute(taskId, task);
			}
		}
	}
	
	public URL getExecutorId() {
		return executorId;
	}
}