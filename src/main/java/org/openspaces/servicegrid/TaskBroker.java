package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.Task;

public interface TaskBroker {

	void addTask(Task task);

	Iterable<Task> takeTasks();

}
