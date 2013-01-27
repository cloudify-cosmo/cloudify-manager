package org.openspaces.servicegrid.service.tasks;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;

public class PlanServiceTask extends ImpersonatingTask {

	private ServiceConfig serviceConfig;
	private List<URI> serviceInstanceIds;
	

	public List<URI> getServiceInstanceIds() {
		return this.serviceInstanceIds;
	}

	public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
		this.serviceInstanceIds = serviceInstanceIds;
	}
	
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}
	
	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
}
