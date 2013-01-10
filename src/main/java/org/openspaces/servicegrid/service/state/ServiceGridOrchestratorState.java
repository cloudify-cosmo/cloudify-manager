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

	public void setPlanned(boolean planned) {
		this.planned = true;
	}
	
	public boolean isPlanned() {
		return this.planned;
	}
}
