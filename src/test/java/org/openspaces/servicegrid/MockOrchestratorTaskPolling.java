package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class MockOrchestratorTaskPolling extends MockTaskPolling {

	private final TaskBroker taskBroker;
	
	private final Orchestrator<? extends TaskExecutorState> getOrchestrator() {
		return (Orchestrator<? extends TaskExecutorState> ) super.getTaskExecutor();
	}
	
	private final URL executorId;
	
	public MockOrchestratorTaskPolling(
			URL executorId,
			TaskBrokerProvider taskBrokerProvider,
			StateHolder stateHolder,
			Orchestrator<?> orchestrator) {
		
		super(executorId, taskBrokerProvider, stateHolder, orchestrator);
		this.executorId = executorId;
		this.taskBroker = taskBrokerProvider.getTaskBroker(executorId);
	}
	
	public void stepTaskOrchestrator() {
		Iterable<? extends Task> newTasks = getOrchestrator().orchestrate();
		for (Task newTask : newTasks) {
			newTask.setSource(executorId);
			taskBroker.postTask(newTask);
		}
	}

}
