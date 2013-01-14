package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.Map;
import java.util.Set;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;

public class ServiceGridPlannerState extends TaskConsumerState {

	private Set<ServiceConfig> servicesConfig = Sets.newLinkedHashSet();
	private boolean deploymentPlanningRequired;
	private ServiceGridDeploymentPlan deploymentPlan;
	private int nextAgentId;
	private Map<URI, Integer> nextServiceInstanceIndexByServiceId;
	private Map<URI, Integer> nextServiceInstanceIndex;
	
	public Set<ServiceConfig> getServices() {
		return servicesConfig;
	}
	
	public void setServices(Set<ServiceConfig> services) {
		this.servicesConfig = services;
	}
	
	@JsonIgnore
	public void addService(ServiceConfig serviceConfig) {
		servicesConfig.add(serviceConfig);
		if (nextServiceInstanceIndex == null) {
			nextServiceInstanceIndex = Maps.newHashMap();
		}
		nextServiceInstanceIndex.put(serviceConfig.getServiceId(), new Integer(0));
		
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

	public int getNextAgentId() {
		return nextAgentId;
	}

	public void setNextAgentId(int nextAgentId) {
		this.nextAgentId = nextAgentId;
	}

	public Map<URI,Integer> getNextServiceInstanceIndexByServiceId() {
		return nextServiceInstanceIndexByServiceId;
	}

	@JsonIgnore
	public int getAndIncrementNextServiceInstanceIndex(URI serviceId) {
		int index = nextServiceInstanceIndex.get(serviceId);
		return nextServiceInstanceIndex.put(serviceId, index+1);
	}

	@JsonIgnore
	public int getAndIncrementNextAgentIndex() {
		return nextAgentId++;
	}

	public void setNextServiceInstanceIndexByServiceId(
			Map<URI, Integer> nextServiceInstanceIndexByServiceId) {
		this.nextServiceInstanceIndexByServiceId = nextServiceInstanceIndexByServiceId;
	}
	
	
}
