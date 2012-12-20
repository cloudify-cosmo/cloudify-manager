package org.openspaces.servicegrid.model.tasks;

import org.openspaces.servicegrid.model.service.ServiceConfig;
import org.openspaces.servicegrid.model.service.ServiceId;

public class InstallServiceTask extends Task{

	private ServiceId serviceId;
	private ServiceConfig serviceConfig;

	public ServiceId getServiceId() {
		return serviceId;
	}

	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public void setServiceId(ServiceId serviceId) {
		this.serviceId = serviceId;		
	}

	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
}
