package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

public class PlanServiceInstanceTask extends ServiceTask {
	
	private URI serviceId;

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
