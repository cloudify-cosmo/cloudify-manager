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
import com.google.common.base.Function;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Predicates;
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

import java.net.URI;
import java.util.List;

/**
 * The placement of instances on agents for all services. Sent from planner to orchestrator.
 * @see ServiceDeploymentPlan
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridDeploymentPlan {

    private List<ServiceDeploymentPlan> services;

    public ServiceGridDeploymentPlan() {
        services = Lists.newArrayList();
    }

    @JsonIgnore
    public void addService(ServiceDeploymentPlan servicePlan) {
        Preconditions.checkArgument(
                !isServiceExists(servicePlan.getServiceConfig().getServiceId()),
                "Service %s already exists",
                servicePlan.getServiceConfig().getServiceId());
        services.add(servicePlan);
    }

    @JsonIgnore
    public void addServiceInstance(URI serviceId, ServiceInstanceDeploymentPlan instancePlan) {
        Preconditions.checkNotNull(serviceId);
        Preconditions.checkArgument(isServiceExists(serviceId), "Unknown service %s", serviceId);
        getServiceById(serviceId).addInstance(instancePlan);
    }

    @JsonIgnore
    public boolean removeServiceInstance(final URI instanceId) {

        for (ServiceDeploymentPlan servicePlan : services) {
            final boolean removed = servicePlan.removeInstanceById(instanceId);
            if (removed) {
                return true;
            }
        }
        return false;
    }

    @JsonIgnore
    public boolean isServiceExists(URI serviceId) {
        return getServiceById(serviceId) != null;
    }

    public List<ServiceDeploymentPlan> getServices() {
        return services;
    }

    public void setServices(List<ServiceDeploymentPlan> services) {
        this.services = services;
    }

    @JsonIgnore
    public ServiceDeploymentPlan getServiceById(final URI serviceId) {
        return Iterables.tryFind(services, new Predicate<ServiceDeploymentPlan>() {

            @Override
            public boolean apply(ServiceDeploymentPlan servicePlan) {
                return serviceId.equals(servicePlan.getServiceConfig().getServiceId());
            }
        }).orNull();
    }

    @JsonIgnore
    public void removeService(final URI serviceId) {

        final boolean removed =
            Iterables.removeIf(services, new Predicate<ServiceDeploymentPlan>() {

                @Override
                public boolean apply(final ServiceDeploymentPlan servicePlan) {
                    return servicePlan.getServiceConfig().getServiceId().equals(serviceId);
                }
            });
        Preconditions.checkArgument(removed, "Service %s does not exist", serviceId);
    }

    @JsonIgnore
    public void replaceServiceById(final URI oldServiceId, final ServiceDeploymentPlan newService) {
        Preconditions.checkArgument(oldServiceId.equals(newService.getServiceConfig().getServiceId()));
        removeService(oldServiceId);
        addService(newService);
    }

    @JsonIgnore
    public Iterable<URI> getInstanceIdsByAgentId(final URI agentId) {
        return Iterables.unmodifiableIterable(
                Iterables.concat(Iterables.transform(services, new Function<ServiceDeploymentPlan, Iterable<URI>>() {

                    @Override
                    public Iterable<URI> apply(ServiceDeploymentPlan servicePlan) {
                        return servicePlan.getInstancesByAgentId(agentId);
                    }
                })));
    }

    @JsonIgnore
    public Iterable<URI> getInstanceIdsByServiceId(URI serviceId) {
        final ServiceDeploymentPlan serviceById = getServiceById(serviceId);
        if (serviceById == null) {
            return Lists.newArrayList();
        }
        return serviceById.getInstanceIds();
    }

    @JsonIgnore
    public Iterable<URI> getServiceIds() {

        Function<ServiceDeploymentPlan, URI> toServiceIdsFunc = new Function<ServiceDeploymentPlan, URI>() {

            @Override
            public URI apply(ServiceDeploymentPlan servicePlan) {
                return servicePlan.getServiceConfig().getServiceId();
            }
        };

        return Iterables.unmodifiableIterable(Iterables.transform(services, toServiceIdsFunc));
    }

    @JsonIgnore
    public Iterable<URI> getAgentIds() {
        Function<ServiceDeploymentPlan, Iterable<URI>> toAgentIdsFunc =
                new Function<ServiceDeploymentPlan, Iterable<URI>>() {

                    @Override
                    public Iterable<URI> apply(ServiceDeploymentPlan servicePlan) {
                        return servicePlan.getAgentIds();
                    }
                };

        return ImmutableSet.copyOf(
                Iterables.concat(
                 Iterables.transform(services, toAgentIdsFunc)));
    }

    public URI getAgentIdByInstanceId(final URI instanceId) {
        Function<ServiceDeploymentPlan, URI> toAgentIdFunc = new Function<ServiceDeploymentPlan, URI>() {

            @Override
            public URI apply(ServiceDeploymentPlan servicePlan) {
                return servicePlan.getAgentIdByInstanceId(instanceId);
            }
        };

        Iterable<URI> agentIds = Iterables.transform(services, toAgentIdFunc);
        Iterable<URI> nonNullAgentIds = Iterables.filter(agentIds, Predicates.notNull());
        return  Iterables.getOnlyElement(nonNullAgentIds, null);
    }

    public URI getServiceIdByInstanceId(final URI instanceId) {
        Predicate<ServiceDeploymentPlan> containsInstanceIdPreicate = new Predicate<ServiceDeploymentPlan>() {

            @Override
            public boolean apply(ServiceDeploymentPlan servicePlan1) {
                return servicePlan1.containsInstanceId(instanceId);
            }
        };
        Optional<ServiceDeploymentPlan> servicePlan = Iterables.tryFind(services, containsInstanceIdPreicate);
        if (!servicePlan.isPresent()) {
            return null;
        }
        return servicePlan.get().getServiceConfig().getServiceId();
    }

    @JsonIgnore
    public String getInstanceDesiredLifecycle(final URI instanceId) {
        Optional<ServiceInstanceDeploymentPlan> instancePlan =
                Iterables.tryFind(Iterables.transform(services,
                        new Function<ServiceDeploymentPlan, ServiceInstanceDeploymentPlan>() {
                            @Override
                            public ServiceInstanceDeploymentPlan apply(
                                    ServiceDeploymentPlan servicePlan) {
                                return servicePlan.getInstanceDeploymentPlan(instanceId).orNull();
                            }
                        }),
                        Predicates.notNull());
        Preconditions.checkState(instancePlan.isPresent());
        return instancePlan.get().getDesiredLifecycle();
    }
}
