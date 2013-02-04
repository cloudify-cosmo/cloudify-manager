package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceConfig;

import com.fasterxml.jackson.annotation.JsonUnwrapped;

public class InstallServiceTask extends Task {
	
	private ServiceConfig serviceConfig;
	
	@JsonUnwrapped
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
}
