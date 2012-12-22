package org.openspaces.servicegrid.model.tasks;

import java.net.URL;
import java.util.Set;

import com.beust.jcommander.internal.Sets;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;

public class TaskExecutorState {

	//Should serialize to List<URL> which is the taskid URLs
	private Set<URL> executingTasks = Sets.newLinkedHashSet();
	private Set<URL> completedTasks = Sets.newLinkedHashSet();
	private Set<URL> pendingTasks = Sets.newLinkedHashSet();
	
	public URL executeFirstPendingTask() {
		URL taskId = getFirstPendingTaskId();
		if (taskId != null) {
			pendingTasks.remove(taskId);
			executingTasks.add(taskId);
		}
		return taskId;
	}
	
	public void completeExecutingTask(URL taskId) {
		boolean remove = executingTasks.remove(taskId);
		Preconditions.checkState(remove,"task " + taskId + " is not executing");
		completedTasks.add(taskId);
	}
	
	public URL getFirstPendingTaskId() {
		return Iterables.getFirst(pendingTasks, null);
	}
	
	public URL getLastCompletedTaskId() {
		return Iterables.getLast(completedTasks, null);
	}
	
	public Iterable<URL> getExecutingTaskIds() {
		return Iterables.unmodifiableIterable(executingTasks);
	}

	public boolean isExecutingTask() {
		return !Iterables.isEmpty(executingTasks);
	}

	public void addPendingTaskId(URL taskId) {
		pendingTasks.add(taskId);
	}
	
	public Iterable<URL> getCompletedTaskIds() {
		return Iterables.unmodifiableIterable(completedTasks);
	}

	public Iterable<URL> getPendingTaskIds() {
		return Iterables.unmodifiableIterable(pendingTasks);
	}
	
}
