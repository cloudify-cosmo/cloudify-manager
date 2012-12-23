package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;

public class MockTaskPolling {

	private final StreamProducer<TaskExecutorState> stateWriter;
	private final TaskExecutor<?> taskExecutor;
	private final URL executorId;
	private final StreamConsumer<Task> taskConsumer;
	private URL lastTaskId;
	
	public MockTaskPolling(URL executorId, StreamProducer<TaskExecutorState> stateWriter, StreamConsumer<Task> taskConsumer, TaskExecutor<?> taskExecutor) {
		this.executorId = executorId;
		this.stateWriter = stateWriter;
		this.taskConsumer = taskConsumer;
		this.taskExecutor = taskExecutor;
	}

	private void afterExecute(URL taskId, Task task) {

		final TaskExecutorState state = taskExecutor.getState();
		state.completeExecutingTask(taskId);
		stateWriter.addElement(getExecutorId(), state);
		
		if (task.getImpersonatedTarget() != null) {
			Preconditions.checkArgument(
					taskExecutor instanceof ImpersonatingTaskExecutor, 
					getExecutorId() + " cannot handle task, since it requires impersonation");
			ImpersonatingTaskExecutor<?,?> impersonatingTaskExecutor = (ImpersonatingTaskExecutor<?,?>) taskExecutor;
			stateWriter.addElement(task.getImpersonatedTarget(), impersonatingTaskExecutor.getImpersonatedState());	
		}
	}

	private void beforeExecute(Task task) {
		Preconditions.checkNotNull(task.getTarget());
		Preconditions.checkArgument(
				task.getTarget().equals(getExecutorId()),
				"Expected task target is %s instead found %s", getExecutorId() , task.getTarget());
		
		final TaskExecutorState state = taskExecutor.getState();
		stateWriter.addElement(getExecutorId(), state);
	}

	public TaskExecutor<? extends TaskExecutorState> getTaskExecutor() {
		return taskExecutor;
	}
	

	public void stepTaskExecutor() {
		
		final TaskExecutorState state = taskExecutor.getState();
		
		if (!state.isExecutingTask()) {
			URL taskId;
			if (lastTaskId == null) {
				taskId = taskConsumer.getFirstElementId(executorId);
			}
			else {
				taskId = taskConsumer.getNextElementId(lastTaskId);
			}
			if (taskId != null) {
				Task task = taskConsumer.getElement(taskId);
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