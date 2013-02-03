package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class ServiceGridOrchestratorParameter {
	
	private URI orchestratorId;
	private URI machineProvisionerId;
	private TaskReader taskReader;
	private StateReader stateReader;
	private CurrentTimeProvider timeProvider;
	
	public TaskReader getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(TaskReader taskReader) {
		this.taskReader = taskReader;
	}

	public StateReader getStateReader() {
		return stateReader;
	}

	public void setStateReader(StateReader stateReader) {
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
}