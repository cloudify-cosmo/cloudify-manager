package org.openspaces.servicegrid.model.tasks;

import java.util.Set;

import com.beust.jcommander.internal.Sets;
import com.google.common.collect.Iterables;

public class TaskExecutorState {

	//Should serialize to List<URL> which is the taskid URLs
	private Set<Task> executingTasks = Sets.newLinkedHashSet();
	private Set<Task> completedTasks = Sets.newLinkedHashSet();
	
	public Task getLastExecutingTask() {
		return Iterables.getLast(executingTasks);
	}

	public void addExecutingTask(Task task) {
		executingTasks.add(task);
	}
	
	public void removeExecutingTask(Task task) {
		executingTasks.remove(task);
	}

	public void addCompletedTask(Task task) {
		completedTasks.add(task);
	}
	
	public Task getLastCompletedTask() {
		return Iterables.getLast(completedTasks);
	}
}
