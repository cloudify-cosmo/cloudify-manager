package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlannerState;

public class UninstallServiceTask extends Task {
	
	public UninstallServiceTask() {
		super(ServiceGridDeploymentPlannerState.class);
	}
	
	private URI serviceId;

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
