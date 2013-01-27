package org.openspaces.servicegrid.agent.tasks;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.ImpersonatingTask;

public class PlanAgentTask  extends ImpersonatingTask {

	private List<URI> serviceInstanceIds;
	public List<URI> getServiceInstanceIds() {
		return this.serviceInstanceIds;
	}

	public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
		this.serviceInstanceIds = serviceInstanceIds;
	}
}
