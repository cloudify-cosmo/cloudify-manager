package org.openspaces.servicegrid.service.state;


import java.net.URI;
import java.util.Set;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.google.common.collect.Sets;

public class ServiceGridOrchestratorState extends TaskConsumerState {

	private ServiceGridDeploymentPlan deploymentPlan;
	private boolean syncedStateWithDeploymentBefore;
	private Set<URI> serviceIdsToUninstall = Sets.<URI>newHashSet();
	private Set<URI> agentIdsToTerminate = Sets.<URI>newHashSet();

	public ServiceGridDeploymentPlan getDeploymentPlan() {
		return deploymentPlan;
	}

	public void setDeploymentPlan(ServiceGridDeploymentPlan deploymentPlan) {
		this.deploymentPlan = deploymentPlan;
	}
	
	public boolean isSyncedStateWithDeploymentBefore() {
		return syncedStateWithDeploymentBefore;
	}

	public void setSyncedStateWithDeploymentBefore(boolean firstSyncStateWithDeployment) {
		this.syncedStateWithDeploymentBefore = firstSyncStateWithDeployment;
	}

	@JsonIgnore
	public void addServiceIdsToUninstall(Iterable<URI> serviceIds) {
		Iterables.addAll(this.serviceIdsToUninstall, serviceIds);
	}

	@JsonIgnore
	public void removeServiceIdToUninstall(URI serviceId) {
		boolean removed = serviceIdsToUninstall.remove(serviceId);
		Preconditions.checkArgument(removed, "Cannot remove %s from services to uninstall list", serviceId);
	}
	
	public Set<URI> getServiceIdsToUninstall() {
		return serviceIdsToUninstall;
	}

	public void setServiceIdsToUninstall(Set<URI> serviceIds) {
		this.serviceIdsToUninstall = serviceIds;
	}


	@JsonIgnore
	public void addAgentIdsToTerminate(Iterable<URI> agentIds) {
		Iterables.addAll(this.agentIdsToTerminate, agentIds);
	}

	@JsonIgnore
	public void removeAgentIdToTerminate(URI agentId) {
		boolean removed = agentIdsToTerminate.remove(agentId);
		Preconditions.checkArgument(removed, "Cannot remove %s from services to uninstall list", agentId);
	}
	
	public Set<URI> getAgentIdsToTerminate() {
		return agentIdsToTerminate;
	}

	public void setAgentIdsToTerminate(Set<URI> agentIds) {
		this.agentIdsToTerminate = agentIds;
	}

	
}
