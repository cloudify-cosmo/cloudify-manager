package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.Task;

public class UninstallServiceTask extends Task {
	
	private URI serviceId;

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
