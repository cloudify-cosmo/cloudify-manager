package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.Task;

import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.ListMultimap;

public class MockTaskBroker implements TaskBroker {

	private final ListMultimap<String, Task> tasksByTag = ArrayListMultimap.create();

	public void addTask(Task task) {
		for(String tag : task.getTags()) {
			tasksByTag.put(tag, task);
		}
	}

	public Iterable<Task> getTasksByTag(String tag) {
		return tasksByTag.get(tag);
	}

	public Iterable<Task> getTasks() {
		// TODO Auto-generated method stub
		return null;
	}

}
