package org.openspaces.servicegrid;

import java.util.ArrayList;

import org.openspaces.servicegrid.model.Task;

import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceOrchestrator implements Orchestrator {

	public Iterable<Task> orchestrate(Iterable<Task> tasks) {
		
		ArrayList<Task> newTasks = Lists.newArrayList();
		
		if (Iterables.isEmpty(tasks)) {
			newTasks.add(new Task());
		}
		
		return newTasks;
	}

}
