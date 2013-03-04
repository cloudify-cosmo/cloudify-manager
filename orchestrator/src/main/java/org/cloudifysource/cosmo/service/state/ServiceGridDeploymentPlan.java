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
    private List<ServiceInstanceDeploymentPlan> instances;
    private List<AgentPlan> agents;

    public ServiceGridDeploymentPlan() {
        services = Lists.newArrayList();
        instances = Lists.newArrayList();
        agents = Lists.newArrayList();
    }

    @JsonIgnore
    public void setService(ServiceDeploymentPlan servicePlan) {
        final URI serviceId = servicePlan.getServiceConfig().getServiceId();
        removeService(serviceId);
        services.add(servicePlan);
    }

    private Predicate<AgentPlan> findAgentIdPredicate(
            final URI agentId) {

        return new Predicate<AgentPlan>() {

            @Override
            public boolean apply(AgentPlan agentPlan) {
                return agentPlan.getAgentId().equals(agentId);
            }
        };
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
    public void addServiceInstance(ServiceInstanceDeploymentPlan instancePlan) {
        final URI instanceId = instancePlan.getInstanceId();
        Preconditions.checkNotNull(instanceId);
        Preconditions.checkNotNull(instancePlan.getAgentId());
        Preconditions.checkNotNull(instancePlan.getStateMachine());

        removeServiceInstance(instanceId);
        instances.add(instancePlan);
    }

    @JsonIgnore
    public boolean removeServiceInstance(final URI instanceId) {
        return Iterables.removeIf(instances, findInstanceIdPredicate(instanceId));
    }

    @JsonIgnore
    public boolean isServiceExists(URI serviceId) {
        return getServicePlan(serviceId).isPresent();
    }

    public List<ServiceDeploymentPlan> getServices() {
        return services;
    }

    public void setServices(List<ServiceDeploymentPlan> services) {
        this.services = services;
    }

    @JsonIgnore
    public Optional<ServiceDeploymentPlan> getServicePlan(final URI serviceId) {
        return Iterables.tryFind(services, new Predicate<ServiceDeploymentPlan>() {

            @Override
            public boolean apply(ServiceDeploymentPlan servicePlan) {
                return serviceId.equals(servicePlan.getServiceConfig().getServiceId());
            }
        });
    }

    @JsonIgnore
    public boolean removeService(final URI serviceId) {

        final boolean removed =
            Iterables.removeIf(services, new Predicate<ServiceDeploymentPlan>() {

                @Override
                public boolean apply(final ServiceDeploymentPlan servicePlan) {
                    return servicePlan.getServiceConfig().getServiceId().equals(serviceId);
                }
            });
        return removed;
    }

    @JsonIgnore
    public void replaceServiceById(final URI oldServiceId, final ServiceDeploymentPlan newService) {
        Preconditions.checkArgument(oldServiceId.equals(newService.getServiceConfig().getServiceId()));
        removeService(oldServiceId);
        setService(newService);
    }

    @JsonIgnore
    public Iterable<URI> getInstanceIdsByAgentId(final URI agentId) {
        Function<ServiceInstanceDeploymentPlan, URI> toInstanceIdFunction =
                new Function<ServiceInstanceDeploymentPlan, URI>() {

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
    public Iterable<URI> getInstanceIdsByServiceId(final URI serviceId) {
        Function<ServiceInstanceDeploymentPlan, URI> toInstanceIdFunction =
                new Function<ServiceInstanceDeploymentPlan, URI>() {

                    @Override
                    public URI apply(ServiceInstanceDeploymentPlan instancePlan) {
                        if (instancePlan.getServiceId().equals(serviceId) &&
                                !instancePlan.getStateMachine().isLifecycleBeginState()) {
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
        Function<AgentPlan, URI> toAgentIdsFunc =
                new Function<AgentPlan, URI>() {

                    @Override
                    public URI apply(AgentPlan agentPlan) {
                        return agentPlan.getAgentId();
                    }
                };

        return Iterables.unmodifiableIterable(Iterables.transform(agents, toAgentIdsFunc));
    }

    public URI getAgentIdByInstanceId(final URI instanceId) {
        return getInstancePlan(instanceId).get().getAgentId();
    }

    public Optional<URI> getServiceIdByInstanceId(final URI instanceId) {
        Optional<ServiceDeploymentPlan> servicePlan = getServiceByInstanceId(instanceId);
        if (!servicePlan.isPresent()) {
            return Optional.absent();
        }
        return Optional.fromNullable(servicePlan.get().getServiceConfig().getServiceId());
    }

    public Optional<ServiceDeploymentPlan> getServiceByInstanceId(final URI instanceId) {
        final Optional<ServiceInstanceDeploymentPlan> instancePlan = getInstancePlan(instanceId);
        if (!instancePlan.isPresent()) {
            return Optional.absent();
        }
        final URI serviceId = instancePlan.get().getServiceId();
        return getServicePlan(serviceId);
    }

    @JsonIgnore
    public Optional<ServiceInstanceDeploymentPlan> getInstancePlan(final URI instanceId) {

        return Iterables.tryFind(instances, findInstanceIdPredicate(instanceId));
    }

    public List<ServiceInstanceDeploymentPlan> getInstances() {
        return instances;
    }

    public void setInstances(List<ServiceInstanceDeploymentPlan> instances) {
        this.instances = instances;
    }

    public Optional<AgentPlan> getAgentPlan(URI agentId) {
        return Iterables.tryFind(agents, findAgentIdPredicate(agentId));
    }

    public void addAgent(AgentPlan agentPlan) {
        final URI agentId = agentPlan.getAgentId();
        Preconditions.checkArgument(!getAgentPlan(agentId).isPresent());
        agents.add(agentPlan);
    }
}
