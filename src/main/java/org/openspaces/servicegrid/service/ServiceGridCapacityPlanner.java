package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.service.state.ServiceGridCapacityPlannerState;

public class ServiceGridCapacityPlanner {

	private final ServiceGridCapacityPlannerState state;
	private final URI deploymentPlannerId;

	public ServiceGridCapacityPlanner(
			ServiceGridCapacityPlannerParameter servicePlannerParameter) {
		this.deploymentPlannerId = servicePlannerParameter.getDeploymentPlannerId();
		this.state = new ServiceGridCapacityPlannerState();
	}
	
	@TaskConsumerStateHolder
	public ServiceGridCapacityPlannerState getState() {
		return this.state;
	}

}
