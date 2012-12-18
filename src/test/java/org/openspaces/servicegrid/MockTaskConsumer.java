package org.openspaces.servicegrid;

public class MockTaskConsumer {

	private final TaskBroker taskBroker;

	public MockTaskConsumer(TaskBroker taskBroker) {
		this.taskBroker = taskBroker;
	}

	public void step() {
		taskBroker.takeTasks();
		
	}

}
