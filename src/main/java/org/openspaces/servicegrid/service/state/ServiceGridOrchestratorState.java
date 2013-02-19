/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
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
