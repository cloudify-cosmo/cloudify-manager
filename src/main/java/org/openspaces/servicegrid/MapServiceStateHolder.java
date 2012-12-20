package org.openspaces.servicegrid;

import java.net.URL;
import java.util.Map;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Maps;

public class MapServiceStateHolder implements StateHolder {

	private final Map<URL, TaskExecutorState> taskExecutorsStateById = Maps.newConcurrentMap();
	
	@Override
	public void putTaskExecutorState(URL executorId, TaskExecutorState state) {
		taskExecutorsStateById.put(executorId, state);
	}
	
	@Override
	public TaskExecutorState getTaskExecutorState(URL executorId) {
		return taskExecutorsStateById.get(executorId);
	}
}
