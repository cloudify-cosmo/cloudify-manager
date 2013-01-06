package org.openspaces.servicegrid.model.tasks;

import java.net.URL;
import java.util.Set;

import org.codehaus.jackson.annotate.JsonIgnore;

import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.google.common.collect.Sets;

public class TaskExecutorState {

	//Should serialize to List<URL> which is the taskid URLs
	private Set<URL> executingTasks = Sets.newLinkedHashSet();
	private Set<URL> completedTasks = Sets.newLinkedHashSet();
	
	public void executeTask(URL taskId) {
		Preconditions.checkNotNull(taskId);
		getExecutingTasks().add(taskId);
	}
	
	public void completeExecutingTask(URL taskId) {
		boolean remove = getExecutingTasks().remove(taskId);
		Preconditions.checkState(remove,"task " + taskId + " is not executing");
		getCompletedTasks().add(taskId);
	}
		
	@JsonIgnore
	public URL getLastCompletedTaskId() {
		return Iterables.getLast(getCompletedTasks(), null);
	}
	
	@JsonIgnore
	public Iterable<URL> getExecutingTaskIds() {
		return Iterables.unmodifiableIterable(getExecutingTasks());
	}

	@JsonIgnore
	public boolean isExecutingTask() {
		return !Iterables.isEmpty(getExecutingTasks());
	}

	@JsonIgnore
	public Iterable<URL> getCompletedTaskIds() {
		return Iterables.unmodifiableIterable(getCompletedTasks());
	}

	public Set<URL> getExecutingTasks() {
		return executingTasks;
	}

	public void setExecutingTasks(Set<URL> executingTasks) {
		this.executingTasks = executingTasks;
	}

	public Set<URL> getCompletedTasks() {
		return completedTasks;
	}

	public void setCompletedTasks(Set<URL> completedTasks) {
		this.completedTasks = completedTasks;
	}
}
