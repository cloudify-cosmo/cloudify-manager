package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.Task;

public interface TaskBroker {

	void addTask(Task installServiceTask);

	Iterable<Task> getTasksByTag(String tag);

	Iterable<Task> getTasks();

}
