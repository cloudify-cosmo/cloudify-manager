package org.openspaces.servicegrid.service.state;

import java.net.URI;

public class ServiceInstanceDeploymentPlan {

	private URI instanceId;
	private URI agentId;
	
	public URI getInstanceId() {
		return instanceId;
	}
	
	public void setInstanceId(URI instanceId) {
		this.instanceId = instanceId;
	}
	
	public URI getAgentId() {
		return agentId;
	}
	
	public void setAgentId(URI agentId) {
		this.agentId = agentId;
	}
}
