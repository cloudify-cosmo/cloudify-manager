package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;

public class ServiceGridCapacityPlannerParameter {

	private URI deploymentPlannerId;
	private StreamReader<Task> taskReader;
	private StreamReader<TaskConsumerState> stateReader;

	public void setDeploymentPlannerId(final URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}

	public StreamReader<TaskConsumerState> getStateReader() {
		return stateReader;
	}

	public StreamReader<Task> getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(StreamReader<Task> taskReader) {
		this.taskReader = taskReader;
	}

	public void setStateReader(StreamReader<TaskConsumerState> stateReader) {
		this.stateReader = stateReader;
	}
}
