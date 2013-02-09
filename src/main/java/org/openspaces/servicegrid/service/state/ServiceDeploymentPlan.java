package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import com.beust.jcommander.internal.Lists;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonUnwrapped;
import com.google.common.base.Function;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Predicates;
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Iterables;

public class ServiceDeploymentPlan {

	private ServiceConfig serviceConfig;
	private List<ServiceInstanceDeploymentPlan> instances;
	
	public ServiceDeploymentPlan() {
		instances = Lists.newArrayList();
	}

	@JsonUnwrapped
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}

	public void setServiceConfig(ServiceConfig service) {
		this.serviceConfig = service;
	}

	public List<ServiceInstanceDeploymentPlan> getInstances() {
		return instances;
	}

	public void setInstances(List<ServiceInstanceDeploymentPlan> instances) {
		this.instances = instances;
	}

	@JsonIgnore
	public boolean removeInstanceById(URI instanceId) {
		return Iterables.removeIf(instances, findInstanceIdPredicate(instanceId));
	}

	private Predicate<ServiceInstanceDeploymentPlan> findInstanceIdPredicate(
			final URI instanceId) {

		return new Predicate<ServiceInstanceDeploymentPlan>() {

			@Override
			public boolean apply(ServiceInstanceDeploymentPlan instancePlan) {
				return instancePlan.getInstanceId().equals(instanceId);
			}
		};
	}

	@JsonIgnore
	public void addInstance(URI instanceId, URI agentId) {
		Preconditions.checkNotNull(instanceId);
		Preconditions.checkNotNull(agentId);
		Preconditions.checkArgument(!Iterables.tryFind(instances, findInstanceIdPredicate(instanceId)).isPresent());
		ServiceInstanceDeploymentPlan instancePlan = new ServiceInstanceDeploymentPlan();
		instancePlan.setInstanceId(instanceId);
		instancePlan.setAgentId(agentId);
		instances.add(instancePlan);
	}

	@JsonIgnore
	public Iterable<URI> getInstancesByAgentId(final URI agentId) {
		Function<ServiceInstanceDeploymentPlan, URI> toInstanceIdFunction = new Function<ServiceInstanceDeploymentPlan, URI>() {

			@Override
			public URI apply(ServiceInstanceDeploymentPlan instancePlan) {
				if (instancePlan.getAgentId().equals(agentId)) {
					return instancePlan.getInstanceId();
				}
				return null;
			}
		};
		return Iterables.unmodifiableIterable(
				Iterables.filter(
				Iterables.transform(instances, toInstanceIdFunction),
				Predicates.notNull()));
	}

	@JsonIgnore
	public Iterable<URI> getInstanceIds() {
		Function<ServiceInstanceDeploymentPlan, URI> toInstanceIdFunction = new Function<ServiceInstanceDeploymentPlan, URI>() {

			@Override
			public URI apply(ServiceInstanceDeploymentPlan instancePlan) {
				return instancePlan.getInstanceId();
			}
		};
		return Iterables.unmodifiableIterable(Iterables.transform(instances, toInstanceIdFunction));
	}

	@JsonIgnore
	public Iterable<URI> getAgentIds() {
		Function<ServiceInstanceDeploymentPlan, URI> toInstanceIdFunction = new Function<ServiceInstanceDeploymentPlan, URI>() {

			@Override
			public URI apply(ServiceInstanceDeploymentPlan instancePlan) {
				return instancePlan.getAgentId();
			}
		};
		return ImmutableSet.copyOf(Iterables.transform(instances, toInstanceIdFunction));
	}

	@JsonIgnore
	public URI getAgentIdByInstanceId(URI instanceId) {
		Optional<ServiceInstanceDeploymentPlan> instancePlan = Iterables.tryFind(instances, findInstanceIdPredicate(instanceId));
		if (!instancePlan.isPresent()) {
			return null;
		}
		
		return instancePlan.get().getAgentId();
	}

	@JsonIgnore
	public boolean containsInstanceId(URI instanceId) {
		return Iterables.tryFind(instances, findInstanceIdPredicate(instanceId)).isPresent();
	}
	
}
