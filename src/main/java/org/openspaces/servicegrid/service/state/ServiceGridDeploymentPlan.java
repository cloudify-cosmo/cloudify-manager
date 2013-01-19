package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;
import java.util.Map.Entry;
import java.util.Set;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.LinkedListMultimap;
import com.google.common.collect.Lists;
import com.google.common.collect.Multimap;
import com.google.common.collect.Sets;

public class ServiceGridDeploymentPlan {

	private List<ServiceConfig> services;
	private LinkedListMultimap<URI,URI> instanceIdsByAgentId;
	private LinkedListMultimap<URI,URI> instanceIdsByServiceId;
	
	public ServiceGridDeploymentPlan() {
		services = Lists.newArrayList();
		instanceIdsByAgentId = LinkedListMultimap.create();
		instanceIdsByServiceId = LinkedListMultimap.create();
	}
	
	@JsonIgnore
	public void addService(ServiceConfig serviceConfig) {
		Preconditions.checkArgument(!isServiceExists(serviceConfig.getServiceId()), "Service %s already exists", serviceConfig.getServiceId());
		services.add(serviceConfig);
	}
	
	@JsonIgnore
	public void addServiceInstance(URI serviceId, URI agentId, URI instanceId) {
		Preconditions.checkArgument(isServiceExists(serviceId), "Unknown service %s", serviceId);
		instanceIdsByAgentId.get(agentId).add(instanceId);
		instanceIdsByServiceId.get(serviceId).add(instanceId);
	}

	@JsonIgnore
	public boolean isServiceExists(URI serviceId) {
		return getServiceById(serviceId) != null;
	}

	public List<ServiceConfig> getServices() {
		return services;
	}

	public void setServices(List<ServiceConfig> services) {
		this.services = services;
	}

	public Multimap<URI,URI> getInstanceIdsByAgentId() {
		return instanceIdsByAgentId;
	}

	public void setInstanceIdsByAgentId(LinkedListMultimap<URI,URI> instanceIdsByAgentId) {
		this.instanceIdsByAgentId = instanceIdsByAgentId;
	}

	public Multimap<URI,URI> getInstanceIdsByServiceId() {
		return instanceIdsByServiceId;
	}

	public void setInstanceIdsByServiceId(LinkedListMultimap<URI,URI> instanceIdsByServiceId) {
		this.instanceIdsByServiceId = instanceIdsByServiceId;
	}

	@JsonIgnore
	public ServiceConfig getServiceById(final URI serviceId) {
		return Iterables.tryFind(services, new Predicate<ServiceConfig>() {

			@Override
			public boolean apply(ServiceConfig service) {
				return serviceId.equals(service.getServiceId());
			}
		}).orNull();
	}

	@JsonIgnore
	public void removeService(final URI serviceId) {
		
		final Set<URI> instanceIdsToRemove = Sets.newHashSet(instanceIdsByServiceId.removeAll(serviceId));
		if (!instanceIdsToRemove.isEmpty()) {
			Iterator<Entry<URI, Collection<URI>>> agentMapIterator = instanceIdsByAgentId.asMap().entrySet().iterator();
			while (agentMapIterator.hasNext()) {
				final Entry<URI, Collection<URI>> entry = agentMapIterator.next();
				final Collection<URI> instanceIds = entry.getValue();
				Iterables.removeIf(instanceIds, new Predicate<URI>(){
	
					@Override
					public boolean apply(URI instanceId) {
						return instanceIdsToRemove.contains(instanceId);
					}
				});
				if (instanceIds.isEmpty()) {
					//remove agent since has no instances
					agentMapIterator.remove();
				}
			}
		}	
		removeServiceInternal(serviceId);
	}

	private void removeServiceInternal(final URI serviceId) {
		final boolean removed =
			Iterables.removeIf(services, new Predicate<ServiceConfig>(){
	
				@Override
				public boolean apply(final ServiceConfig serviceConfig) {
					return serviceConfig.getServiceId().equals(serviceId);
				}
			});
		Preconditions.checkArgument(removed, "Service %s does not exist", serviceId);
	}

	@JsonIgnore
	public void replaceService(ServiceConfig oldService, ServiceConfig newService) {
		final URI oldServiceId = oldService.getServiceId();
		Preconditions.checkArgument(oldServiceId.equals(newService.getServiceId()));
		removeServiceInternal(oldServiceId);
		addService(newService);
	}
}
