package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class ServiceGridOrchestratorParameter {
	
	private URI orchestratorId;
	private URI machineProvisionerId;
	private StreamReader<Task> taskReader;
	private StreamReader<TaskConsumerState> stateReader;
	private CurrentTimeProvider timeProvider;
	private URI deploymentPlannerId;
	
	public StreamReader<Task> getTaskReader() {
		return taskReader;
	}

	public void setTaskConsumer(StreamReader<Task> taskReader) {
		this.taskReader = taskReader;
	}

	public StreamReader<TaskConsumerState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamReader<TaskConsumerState> stateReader) {
		this.stateReader = stateReader;
	}

	public URI getOrchestratorId() {
		return orchestratorId;
	}

	public void setOrchestratorId(URI id) {
		this.orchestratorId = id;
	}

	public URI getMachineProvisionerId() {
		return machineProvisionerId;
	}

	public void setMachineProvisionerId(URI cloudExecutorId) {
		this.machineProvisionerId = cloudExecutorId;
	}

	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}

	public void setDeploymentPlannerId(URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}
}