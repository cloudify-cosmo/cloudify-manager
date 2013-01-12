package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.LinkedListMultimap;
import com.google.common.collect.Lists;
import com.google.common.collect.Multimap;

public class ServiceGridFloorPlan {

	private List<ServiceConfig> services;
	private LinkedListMultimap<URI,URI> instanceIdsByAgentId;
	private LinkedListMultimap<URI,URI> instanceIdsByServiceId;
	
	public ServiceGridFloorPlan() {
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
	public void removeService(ServiceConfig service) {
		Preconditions.checkArgument(isServiceExists(service.getServiceId()), "Service %s does not exist", service.getServiceId());
		services.remove(service);		
	}
}
