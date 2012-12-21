package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class MockTaskPolling {

	private final StateHolder stateHolder;
	private final TaskExecutor<?> taskExecutor;
	private final URL executorId;
	private final TaskBroker taskBroker;
	
	public MockTaskPolling(URL executorId, TaskBrokerProvider taskBrokerProvider, StateHolder stateHolder, TaskExecutor<?> taskExecutor) {
		this.executorId = executorId;
		this.stateHolder = stateHolder;
		this.taskExecutor = taskExecutor;
		this.taskBroker = taskBrokerProvider.getTaskBroker(executorId);
	}

	private void afterExecute(Task task) {

		final TaskExecutorState state = taskExecutor.getState();
		state.removeExecutingTask(task);
		state.addCompletedTask(task);
		stateHolder.putTaskExecutorState(executorId, state);
		
		if (task.getImpersonatedTarget() != null) {
			if (! (taskExecutor instanceof ImpersonatingTaskExecutor)) {
				throw new IllegalArgumentException(executorId + " cannot handler task, since it requires impersonation");
			}
			ImpersonatingTaskExecutor<?,?> impersonatingTaskExecutor = (ImpersonatingTaskExecutor<?,?>) taskExecutor;
			stateHolder.putTaskExecutorState(task.getImpersonatedTarget(), impersonatingTaskExecutor.getImpersonatedState());	
		}
	}

	private void beforeExecute(Task task) {
	
		if (!task.getTarget().equals(executorId)) {
			throw new IllegalArgumentException("Expected task target is " + executorId + " instead found " + task.getTarget());
		}
		final TaskExecutorState state = taskExecutor.getState();
		state.addExecutingTask(task);
		stateHolder.putTaskExecutorState(executorId, state);
	}

	public TaskExecutor<? extends TaskExecutorState> getTaskExecutor() {
		return taskExecutor;
	}
	

	public void stepTaskExecutor() {
		
		Iterable<Task> tasks = taskBroker.getNextTasks();
		for (Task task : tasks) {
			beforeExecute(task);
			taskExecutor.execute(task);
			afterExecute(task);
		}
	}

}
