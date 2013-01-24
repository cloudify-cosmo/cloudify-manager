package org.openspaces.servicegrid.service;

import java.net.URI;

public class ServiceGridCapacityPlannerParameter {

	private URI deploymentPlannerId;

	public void setDeploymentPlannerId(final URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}
	
	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}
}
