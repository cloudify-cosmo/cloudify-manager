package org.openspaces.servicegrid.service.state;

import java.util.Set;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.collect.Sets;

public class ServiceGridPlannerState extends TaskConsumerState {

	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet();
	private boolean deploymentPlanningRequired;
	private ServiceGridDeploymentPlan deploymentPlan;
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	@JsonIgnore
	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
		setDeploymentPlanningRequired(true);
	}

	public void setDeploymentPlanningRequired(boolean deploymentPlanningRequired) {
		this.deploymentPlanningRequired = deploymentPlanningRequired;
	}
	
	public boolean isDeploymentPlanningRequired() {
		return deploymentPlanningRequired;
	}

	public ServiceGridDeploymentPlan getDeploymentPlan() {
		return deploymentPlan;
	}

	public void setDeploymentPlan(ServiceGridDeploymentPlan deploymentPlan) {
		this.deploymentPlan = deploymentPlan;
	}

	@JsonIgnore
	public void updateService(ServiceConfig serviceConfig) {
		setDeploymentPlanningRequired(true);
	}
}
