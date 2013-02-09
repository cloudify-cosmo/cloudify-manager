package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.state.StateReader;

public class ServiceGridCapacityPlannerParameter {

	private URI deploymentPlannerId;
	private TaskReader taskReader;
	private StateReader stateReader;
	private URI capacityPlannerId;

	public void setDeploymentPlannerId(final URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}

	public StateReader getStateReader() {
		return stateReader;
	}

	public TaskReader getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(TaskReader taskReader) {
		this.taskReader = taskReader;
	}

	public void setStateReader(StateReader stateReader) {
		this.stateReader = stateReader;
	}

	public URI getCapacityPlannerId() {
		return capacityPlannerId;
	}

	public void setCapacityPlannerId(URI capacityPlannerId) {
		this.capacityPlannerId = capacityPlannerId;
	}
}
