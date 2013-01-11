package org.openspaces.servicegrid;

import java.net.URI;
import java.util.List;

import org.codehaus.jackson.annotate.JsonIgnore;

import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class TaskConsumerState {

	//Should serialize to List<URI> which is the taskid URIs
	private List<URI> executingTasks = Lists.newArrayList();
	private List<URI> completedTasks = Lists.newArrayList();
	
	public void executeTask(URI taskId) {
		Preconditions.checkNotNull(taskId);
		getExecutingTasks().add(taskId);
	}
	
	public void completeExecutingTask(URI taskId) {
		boolean remove = getExecutingTasks().remove(taskId);
		Preconditions.checkState(remove,"task " + taskId + " is not executing");
		getCompletedTasks().add(taskId);
	}
		
	@JsonIgnore
	public URI getLastCompletedTaskId() {
		return Iterables.getLast(getCompletedTasks(), null);
	}
	
	@JsonIgnore
	public boolean isExecutingTask() {
		return !Iterables.isEmpty(getExecutingTasks());
	}

	public List<URI> getExecutingTasks() {
		return executingTasks;
	}

	public void setExecutingTasks(List<URI> executingTasks) {
		this.executingTasks = executingTasks;
	}

	public List<URI> getCompletedTasks() {
		return completedTasks;
	}

	public void setCompletedTasks(List<URI> completedTasks) {
		this.completedTasks = completedTasks;
	}
}
