package org.openspaces.servicegrid.model.service;

import java.net.URL;
import java.util.Set;

import org.openspaces.servicegrid.ServiceConfig;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceGridOrchestratorState extends TaskExecutorState {

	private Set<URL> agents = Sets.newLinkedHashSet();
	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet(); 
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	public Set<URL> getAgents() {
		return agents;
	}
	
	public void setAgents(Set<URL> agents) {
		this.agents = agents;
	}

	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
	}

}
