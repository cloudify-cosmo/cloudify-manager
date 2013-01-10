package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.TaskExecutorState;

public class ServiceState extends TaskExecutorState {
	
	private List<URI> instanceIds;
	
	private ServiceConfig serviceConfig;
	
	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public List<URI> getInstanceIds() {
		return instanceIds;
	}
	
	public void setInstanceIds(List<URI> instanceIds) {
		this.instanceIds = instanceIds;
	}
}
