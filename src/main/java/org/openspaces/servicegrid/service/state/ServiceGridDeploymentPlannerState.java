package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

public class ServiceGridDeploymentPlannerState extends TaskConsumerState {

	private ServiceGridCapacityPlan capacityPlan;
	private boolean deploymentPlanningRequired;
	private ServiceGridDeploymentPlan deploymentPlan;
	private int nextAgentId;
	private Map<URI, Integer> nextServiceInstanceIndexByServiceId;
	private Map<URI, Integer> nextServiceInstanceIndex;
	
	public ServiceGridDeploymentPlannerState() {
		capacityPlan = new ServiceGridCapacityPlan();
		deploymentPlan = new ServiceGridDeploymentPlan();
	}
	
	public ServiceGridCapacityPlan getCapacityPlan() {
		return capacityPlan;
	}
	
	public void setCapacityPlan(ServiceGridCapacityPlan services) {
		this.capacityPlan = services;
	}
	
	@JsonIgnore
	public void updateCapacityPlan(ServiceConfig serviceConfig) {
		capacityPlan.addService(serviceConfig);
		if (nextServiceInstanceIndex == null) {
			nextServiceInstanceIndex = Maps.newHashMap();
		}
		nextServiceInstanceIndex.put(serviceConfig.getServiceId(), new Integer(0));
		
		setDeploymentPlanningRequired(true);
	}
	
	@JsonIgnore
	public void removeService(final URI serviceId) {
		capacityPlan.removeServiceById(serviceId);		
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
		nextServiceInstanceIndex.put(serviceId, index+1);
		return index;
	}

	@JsonIgnore
	public int getAndDecrementNextServiceInstanceIndex(URI serviceId) {
		int lastIndex = nextServiceInstanceIndex.get(serviceId)-1;
		Preconditions.checkState(lastIndex > 0, "cannot decrement service instance index");
		nextServiceInstanceIndex.put(serviceId, lastIndex);
		return lastIndex;
	}
	
	@JsonIgnore
	public int getAndIncrementNextAgentIndex() {
		return nextAgentId++;
	}

	public void setNextServiceInstanceIndexByServiceId(
			Map<URI, Integer> nextServiceInstanceIndexByServiceId) {
		this.nextServiceInstanceIndexByServiceId = nextServiceInstanceIndexByServiceId;
	}

	public ServiceConfig getServiceById(final URI serviceId) {
		return capacityPlan.getServiceById(serviceId);
	}
}
