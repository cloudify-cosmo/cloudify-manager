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
package org.cloudifysource.cosmo.service.state;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

import java.net.URI;
import java.util.List;

/**
 *  Holds the capacity plan for each service.
 *
 *  @author Itai Frenkel
 *  @since 0.1
 */
public class ServiceGridCapacityPlan {

    private List<ServiceConfig> services = Lists.newArrayList();
    private List<ServiceConfig> removedServices = Lists.newArrayList();

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
        removedServices.remove(serviceId);
        services.add(serviceConfig);
    }

    @JsonIgnore
    public void removeServiceById(final URI serviceId) {
        Preconditions.checkNotNull(serviceId);
        final Optional<ServiceConfig> serviceConfig =
                Iterables.tryFind(services, findServiceIdPredicate(serviceId));
        if (serviceConfig.isPresent()) {
            Preconditions.checkState(!Iterables.any(removedServices, findServiceIdPredicate(serviceId)));
            removedServices.add(serviceConfig.get());
        }
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

    public List<ServiceConfig> getRemovedServices() {
        return removedServices;
    }

    public void setRemovedServices(List<ServiceConfig> removedServices) {
        this.removedServices = removedServices;
    }
}
