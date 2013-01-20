package org.openspaces.servicegrid.service.state;


import java.net.URI;
import java.util.Collection;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
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
	
	@JsonIgnore
	public Iterable<URI> getServiceInstanceIdsOfService(URI serviceId) {
		return Iterables.unmodifiableIterable(deploymentPlan.getInstanceIdsByServiceId().get(serviceId));
	}

	@JsonIgnore
	public Iterable<URI> getServiceInstanceIdsOfAgent(URI agentId) {
		return Iterables.unmodifiableIterable(deploymentPlan.getInstanceIdsByAgentId().get(agentId));
	}
	
	@JsonIgnore
	public Iterable<ServiceConfig> getServices() {
		return Iterables.unmodifiableIterable(deploymentPlan.getServices());
	}
	
	@JsonIgnore
	public Iterable<URI> getServiceIds() {
		return Iterables.transform(deploymentPlan.getServices(), new Function<ServiceConfig,URI>(){

			@Override
			public URI apply(ServiceConfig serviceConfig) {
				return serviceConfig.getServiceId();
			}
		});
	}
	
	@JsonIgnore
	public Iterable<URI> getAgentIds() {
		return Iterables.unmodifiableIterable(deploymentPlan.getInstanceIdsByAgentId().keySet());
	}

	@JsonIgnore
	public URI getAgentIdOfServiceInstance(final URI instanceId) {
		final Collection<Entry<URI, URI>> instanceIdByAgentId = deploymentPlan.getInstanceIdsByAgentId().entries();
		final Entry<URI, URI> entryNotFound = null;
		final Entry<URI, URI> entry = Iterables.find(instanceIdByAgentId, new Predicate<Map.Entry<URI,URI>>() {

					@Override
					public boolean apply(Map.Entry<URI,URI> entry) {
						return instanceId.equals(entry.getValue());
					}
		}, entryNotFound);
		return entry != entryNotFound ? entry.getKey() : null;
	}

	@JsonIgnore
	public URI getServiceIdOfServiceInstance(final URI instanceId) {
		final Collection<Entry<URI, URI>> instanceIdByServiceId = deploymentPlan.getInstanceIdsByServiceId().entries();
		final Entry<URI, URI> entryNotFound = null;
		final Entry<URI, URI> entry = Iterables.find(instanceIdByServiceId, new Predicate<Map.Entry<URI,URI>>() {

					@Override
					public boolean apply(Map.Entry<URI,URI> entry) {
						return instanceId.equals(entry.getValue());
					}
		}, entryNotFound);
		return entry != entryNotFound ? entry.getKey() : null;
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
