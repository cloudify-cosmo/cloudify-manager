package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTask;

public class RecoverServiceInstanceStateTask extends ImpersonatingTask {

	private URI serviceId;

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}
		

}
