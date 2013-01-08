package org.openspaces.servicegrid.model.service;

import java.util.Set;

import org.openspaces.servicegrid.ServiceConfig;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceGridOrchestratorState extends TaskExecutorState {

	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet(); 
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
	}
}
