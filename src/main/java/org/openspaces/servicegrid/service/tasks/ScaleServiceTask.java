package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlannerState;

public class ScaleServiceTask extends Task {

	public ScaleServiceTask() {
		super(ServiceGridDeploymentPlannerState.class);
	}
	
	private int plannedNumberOfInstances;
	private URI serviceId;

	public void setPlannedNumberOfInstances(int plannedNumberOfInstances) {
		this.plannedNumberOfInstances = plannedNumberOfInstances;
	}
	
	public int getPlannedNumberOfInstances() {
		return plannedNumberOfInstances;
	}

	public URI getServiceId() {
		return serviceId;
	}
	
	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}
}
