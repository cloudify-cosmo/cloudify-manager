package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.HashMap;
import java.util.List;

import org.openspaces.servicegrid.model.tasks.Task;

import com.beust.jcommander.internal.Lists;
import com.google.common.base.Throwables;
import com.google.common.collect.ArrayListMultimap;
import com.google.common.collect.ListMultimap;
import com.google.common.collect.Maps;

public class MockTaskBrokerProvider implements TaskBrokerProvider {

	private final ListMultimap<URL, Task> tasksByTarget = ArrayListMultimap.create();
	private final HashMap<URL, Task> tasksById = Maps.newHashMap();

	private int id;
	
	public MockTaskBrokerProvider() {
	}
	
	public TaskBroker getTaskBroker(final URL targetExecutorId) {
		return new TaskBroker() {

			public Iterable<Task> getNextTasks() {
				List<Task> tasks = Lists.newArrayList();
				tasks.addAll(tasksByTarget.removeAll(targetExecutorId));
				return tasks;
			}

			public URL postTask(Task task) {
				tasksByTarget.put(task.getTarget(), task);
				try {
					URL url = new URL("http://localhost/tasks/"+id);
					tasksById.put(url, task);
					id++;
					return url;
				} catch (MalformedURLException e) {
					 throw Throwables.propagate(e);
				}
			}
		};
	}
	
}
