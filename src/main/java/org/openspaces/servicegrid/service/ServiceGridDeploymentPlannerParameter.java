package org.openspaces.servicegrid.service;

import java.net.URI;

public class ServiceGridDeploymentPlannerParameter {
	
	private URI orchestratorId;
	private URI agentsId;
	private URI deploymentPlannerId;
	
	public URI getOrchestratorId() {
		return orchestratorId;
	}

	public void setOrchestratorId(URI orchestratorId) {
		this.orchestratorId = orchestratorId;
	}

	public URI getAgentsId() {
		return agentsId;
	}

	public void setAgentsId(URI agentsId) {
		this.agentsId = agentsId;
	}

	public void setDeploymentPlannerId(URI deploymentPlannerId) {
		this.deploymentPlannerId = deploymentPlannerId;
	}

	public URI getDeploymentPlannerId() {
		return deploymentPlannerId;
	}
}
