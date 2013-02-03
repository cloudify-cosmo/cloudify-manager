package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class PlanServiceInstanceTask extends ImpersonatingTask {
	
	public PlanServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

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
