package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;

public interface TaskBroker {

	URL postTask(Task task);

	/**
	 * @return The next list of tasks, or empty iterable if no tasks pending.
	 * Does not block waiting for a new task.
	 */
	Iterable<Task> getNextTasks();

}
