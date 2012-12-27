package org.openspaces.servicegrid.model.service;

import org.openspaces.servicegrid.ServiceConfig;



public class InstallServiceTask extends ServiceTask {
	
	private ServiceConfig serviceConfig;
	

	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
}
