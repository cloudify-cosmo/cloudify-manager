package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlan;

public class UpdateDeploymentPlanTask extends Task {

	private ServiceGridDeploymentPlan deploymentPlan;

	public ServiceGridDeploymentPlan getDeploymentPlan() {
		return deploymentPlan;
	}

	public void setDeploymentPlan(ServiceGridDeploymentPlan deploymentPlan) {
		this.deploymentPlan = deploymentPlan;
	}

}
