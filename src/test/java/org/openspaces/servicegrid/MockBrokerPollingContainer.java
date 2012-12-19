package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.Task;

public class MockBrokerPollingContainer {

	private final TaskBroker taskBroker;
	private final Orchestrator orchestrator;

	public MockBrokerPollingContainer(
			TaskBroker taskBroker,
			Orchestrator orchestrator) {

		this.taskBroker = taskBroker;
		this.orchestrator = orchestrator;
	}

	public void step() {
		
		Iterable<Task> tasks = taskBroker.takeTasks();
		Iterable<Task> newTasks = orchestrator.orchestrate(tasks);
		for (Task newTask : newTasks) {
			taskBroker.addTask(newTask);
		}
	}

}
