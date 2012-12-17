package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.Task;

public class MockTaskProducer {

	private final TaskBroker taskBroker;
	private final Orchestrator orchestrator;

	public MockTaskProducer(
			TaskBroker taskBroker,
			Orchestrator orchestrator) {

		this.taskBroker = taskBroker;
		this.orchestrator = orchestrator;
	}

	public void step() {
		
		Iterable<Task> tasks = taskBroker.getTasks();
		Iterable<Task> newTasks = orchestrator.orchestrate(tasks);
		for (Task newTask : newTasks) {
			taskBroker.addTask(newTask);
		}
	}

}
