package org.openspaces.servicegrid.service.state;

import java.util.Set;

import org.openspaces.servicegrid.TaskConsumerState;

import com.google.common.collect.Sets;

public class ServiceGridOrchestratorState extends TaskConsumerState {

	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet();
	private boolean floorPlanningRequired; 
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
	}

	public void setFloorPlanningRequired(boolean floorPlanningRequired) {
		this.floorPlanningRequired = floorPlanningRequired;
	}
	
	public boolean FloorPlanningRequired() {
		return floorPlanningRequired;
	}
}
