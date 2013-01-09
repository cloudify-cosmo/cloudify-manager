package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

public class PlanServiceInstanceTask extends ServiceTask {
	
	private URI serviceId;
	private URI agentId;

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

	public URI getAgentId() {
		return agentId;
	}

	public void setAgentId(URI agentId) {
		this.agentId = agentId;
	}
	
}
