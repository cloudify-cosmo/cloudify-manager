package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.base.Throwables;

public class MockServiceOrchestratorTaskExecutor {

	private final TaskBroker taskBroker;
	private final Orchestrator<? extends TaskExecutorState, ? extends Task> orchestrator;
	private final StateHolder stateHolder;
	private URL executorId;
	
	public MockServiceOrchestratorTaskExecutor(
			TaskBrokerProvider taskBrokerProvider,
			StateHolder stateHolder,
			Orchestrator<?,?> orchestrator) {

		try {
			this.executorId = new URL("http://localhost/executors/"+orchestrator.getId());
		} catch (MalformedURLException e) {
			Throwables.propagate(e);
		}
		this.taskBroker = taskBrokerProvider.getTaskBroker(executorId);
		this.orchestrator = orchestrator;
		this.stateHolder = stateHolder;
	}

	public void stepTaskExecutor() {
		
		Iterable<Task> tasks = taskBroker.getNextTasks();
		for (Task task : tasks) {
			beforeExecute(task);
			orchestrator.execute(task);
			afterExecute(task);
		}
	}

	private void afterExecute(Task task) {

		final TaskExecutorState state = orchestrator.getState();
		state.removeExecutingTask(task);
		state.addCompletedTask(task);
		stateHolder.putTaskExecutorState(executorId, state);	
	}

	private void beforeExecute(Task task) {
		{
			final TaskExecutorState state = orchestrator.getState();
			state.addExecutingTask(task);
			stateHolder.putTaskExecutorState(executorId, state);
		}
	}
	
	/*
	public void stepOrchestrator() {
		orchestrator.orchestrate();
		Iterable<? extends Task> newTasks = orchestrator.orchestrate();
		for (Task newTask : newTasks) {
			taskBroker.postTask(newTask);
		}
	}*/

}
