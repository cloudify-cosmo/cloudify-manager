package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class ServiceGridPlannerParameter {
	
	private URI plannerExecutorId;
	private StreamReader<TaskConsumerState> stateReader;
	private CurrentTimeProvider timeProvider;
	
	public StreamReader<TaskConsumerState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamReader<TaskConsumerState> stateReader) {
		this.stateReader = stateReader;
	}

	public URI getPlannerExecutorId() {
		return plannerExecutorId;
	}

	public void setFloorPlannerExecutorId(URI orchestratorExecutorId) {
		this.plannerExecutorId = orchestratorExecutorId;
	}

	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}
	
}
