package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;

public class PlanServiceTask extends ImpersonatingTask {

	private ServiceConfig serviceConfig;

	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}
	
	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
}
