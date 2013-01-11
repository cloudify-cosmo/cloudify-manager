package org.openspaces.servicegrid.service.state;

import java.util.Set;

import org.openspaces.servicegrid.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceGridOrchestratorState extends TaskExecutorState {

	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet();
	private boolean planned; 
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
	}

	public void setFloorPlanned(boolean planned) {
		this.planned = planned;
	}
	
	public boolean isFloorPlanned() {
		return this.planned;
	}
}
