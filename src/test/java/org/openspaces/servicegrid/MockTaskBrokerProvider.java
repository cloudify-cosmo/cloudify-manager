package org.openspaces.servicegrid;

import java.util.List;

import org.openspaces.servicegrid.model.Task;

import com.beust.jcommander.internal.Lists;
import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.ListMultimap;

public class MockTaskBrokerProvider implements TaskBrokerProvider {

	private final ListMultimap<String, Task> tasksByTag = ArrayListMultimap.create();

	public MockTaskBrokerProvider() {
	}
	
	public TaskBroker getTaskBroker(final String target) {
		return new TaskBroker() {

			public Iterable<Task> takeTasks() {
				List<Task> tasks = Lists.newArrayList();
				tasks.addAll(tasksByTag.removeAll(target));
				return tasks;
			}

			public void addTask(Task task) {

				for (String tag : task.getTags())
					tasksByTag.put(tag, task);

			}
		};
	}
	
}
