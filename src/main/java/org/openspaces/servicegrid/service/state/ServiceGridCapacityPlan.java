package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridCapacityPlan {

	private List<ServiceConfig> services = Lists.newArrayList();

	public List<ServiceConfig> getServices() {
		return services;
	}

	public void setServices(List<ServiceConfig> services) {
		this.services = services;
	}

	@JsonIgnore
	public void addService(final ServiceConfig serviceConfig) {
		final URI serviceId = serviceConfig.getServiceId();
		Preconditions.checkArgument(!Iterables.tryFind(services, findServiceIdPredicate(serviceId)).isPresent());
		services.add(serviceConfig);
	}

	@JsonIgnore
	public void removeServiceById(final URI serviceId) {
		Preconditions.checkNotNull(serviceId);
		Iterables.removeIf(services, findServiceIdPredicate(serviceId));		
	}

	private Predicate<ServiceConfig> findServiceIdPredicate(final URI serviceId) {
		final Predicate<ServiceConfig> findServiceIdPredicate = new Predicate<ServiceConfig>() {

			@Override
			public boolean apply(final ServiceConfig serviceConfig) {
				return serviceConfig.getServiceId().equals(serviceId);
			}
		};
		return findServiceIdPredicate;
	}

	public ServiceConfig getServiceById(URI serviceId) {
		Preconditions.checkNotNull(serviceId);
		return Iterables.tryFind(services, findServiceIdPredicate(serviceId)).orNull();
	}
}
