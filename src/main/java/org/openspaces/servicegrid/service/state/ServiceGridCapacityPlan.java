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
