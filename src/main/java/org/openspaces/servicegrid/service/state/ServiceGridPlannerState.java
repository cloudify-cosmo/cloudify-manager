package org.openspaces.servicegrid.service.state;

import java.util.Set;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.collect.Sets;

public class ServiceGridPlannerState extends TaskConsumerState {

	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet();
	private boolean floorPlanningRequired;
	private ServiceGridFloorPlan floorPlan;
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	@JsonIgnore
	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
		setFloorPlanningRequired(true);
	}

	public void setFloorPlanningRequired(boolean floorPlanningRequired) {
		this.floorPlanningRequired = floorPlanningRequired;
	}
	
	public boolean isFloorPlanningRequired() {
		return floorPlanningRequired;
	}

	public ServiceGridFloorPlan getFloorPlan() {
		return floorPlan;
	}

	public void setFloorPlan(ServiceGridFloorPlan floorPlan) {
		this.floorPlan = floorPlan;
	}

	@JsonIgnore
	public void updateService(ServiceConfig serviceConfig) {
		setFloorPlanningRequired(true);
	}
}
