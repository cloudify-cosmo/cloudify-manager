package org.openspaces.servicegrid.model.tasks;

import org.openspaces.servicegrid.model.service.ServiceConfig;

public class SetServiceConfigTask extends Task{

	private ServiceConfig serviceConfig;

	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
}
