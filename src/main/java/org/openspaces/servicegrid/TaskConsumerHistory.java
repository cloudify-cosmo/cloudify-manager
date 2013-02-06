package org.openspaces.servicegrid;

import java.util.List;

import com.google.common.collect.Lists;

public class TaskConsumerHistory {

	private List<Task> tasksHistory = Lists.newArrayList();

	public List<Task> getTasksHistory() {
		return tasksHistory;
	}

	public void setTasksHistory(List<Task> tasksHistory) {
		this.tasksHistory = tasksHistory;
	}
}
