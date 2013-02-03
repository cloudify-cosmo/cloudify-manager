package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class RecoverServiceInstanceStateTask extends ImpersonatingTask {

	public RecoverServiceInstanceStateTask() {
		super(ServiceInstanceState.class);
	}
	
	private URI serviceId;

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}
		

}
