package org.openspaces.servicegrid.service.tasks;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceState;

import com.fasterxml.jackson.annotation.JsonUnwrapped;

public class PlanServiceTask extends Task {

	public PlanServiceTask() {
		super(ServiceState.class);
	}

	private ServiceConfig serviceConfig;
	private List<URI> serviceInstanceIds;
	

	public List<URI> getServiceInstanceIds() {
		return this.serviceInstanceIds;
	}

	public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
		this.serviceInstanceIds = serviceInstanceIds;
	}
	
	@JsonUnwrapped
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}
	
	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
}
