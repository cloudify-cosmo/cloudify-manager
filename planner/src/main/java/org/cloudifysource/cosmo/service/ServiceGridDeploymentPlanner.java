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
package org.cloudifysource.cosmo.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerState;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskProducer;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlannerState;
import org.cloudifysource.cosmo.service.state.ServiceInstanceDeploymentPlan;
import org.cloudifysource.cosmo.service.tasks.InstallServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScaleServiceTask;
import org.cloudifysource.cosmo.service.tasks.UninstallServiceTask;
import org.cloudifysource.cosmo.service.tasks.UpdateDeploymentPlanTask;
import org.cloudifysource.cosmo.streams.StreamUtils;

import java.net.URI;
import java.util.List;
import java.util.Set;

/**
 * Translates the capacity plan (number of instances per service) into a deployment plan (places instances in
 * machines).
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridDeploymentPlanner {

    private final ServiceGridDeploymentPlannerState state;
    private final URI orchestratorId;
    private final ObjectMapper mapper;
    private final URI agentsId;

    public ServiceGridDeploymentPlanner(ServiceGridDeploymentPlannerParameter parameterObject) {
        this.orchestratorId = parameterObject.getOrchestratorId();
        this.agentsId = parameterObject.getAgentsId();
        this.state = new ServiceGridDeploymentPlannerState();
        this.state.setTasksHistory(ServiceUtils.toTasksHistoryId(parameterObject.getDeploymentPlannerId()));
        mapper = StreamUtils.newObjectMapper();
    }

    @TaskConsumer(persistTask = true)
    public void scaleService(final ScaleServiceTask task) {

        URI serviceId = task.getServiceId();
        ServiceConfig serviceConfig = state.getServiceById(serviceId);
        Preconditions.checkNotNull(serviceConfig, "Cannot find service %s", serviceId);

        final int newPlannedNumberOfInstances = task.getPlannedNumberOfInstances();
        final int maxNumberOfInstances = serviceConfig.getMaxNumberOfInstances();
        Preconditions.checkArgument(
                newPlannedNumberOfInstances <= maxNumberOfInstances,
                "Cannot scale above max number of instances %s", maxNumberOfInstances);
        final int minNumberOfInstances = serviceConfig.getMinNumberOfInstances();
        Preconditions.checkArgument(
                newPlannedNumberOfInstances >= minNumberOfInstances,
                "Cannot scale above min number of instances %s", minNumberOfInstances);

        if (serviceConfig.getPlannedNumberOfInstances() != newPlannedNumberOfInstances) {
            serviceConfig.setPlannedNumberOfInstances(newPlannedNumberOfInstances);
            state.updateService(serviceConfig);
        }
    }

    @TaskConsumer(persistTask = true)
    public void installService(final InstallServiceTask task) {

        final ServiceConfig serviceConfig = task.getServiceConfig();
        Preconditions.checkNotNull(serviceConfig);
        Preconditions.checkArgument(
                serviceConfig.getPlannedNumberOfInstances() <= serviceConfig.getMaxNumberOfInstances(),
                "Cannot scale above max number of instances %s", serviceConfig.getMaxNumberOfInstances());
        Preconditions.checkArgument(
                serviceConfig.getPlannedNumberOfInstances() >= serviceConfig.getMinNumberOfInstances(),
                "Cannot scale below min number of instances %s", serviceConfig.getMinNumberOfInstances());

        final URI serviceId = serviceConfig.getServiceId();
        checkServiceId(serviceId);
        boolean installed = isServiceInstalled(serviceId);
        Preconditions.checkState(!installed);
        state.updateCapacityPlan(serviceConfig);
    }

    @TaskConsumer(persistTask = true)
    public void uninstallService(final UninstallServiceTask task) {
        URI serviceId = task.getServiceId();
        checkServiceId(serviceId);
        boolean installed = isServiceInstalled(serviceId);
        Preconditions.checkState(installed);
        state.removeService(serviceId);
    }

    @TaskProducer
    public Iterable<Task> deploymentPlan() {

        List<Task> newTasks = Lists.newArrayList();
        if (state.isDeploymentPlanningRequired()) {
            updateDeploymentPlan();

            UpdateDeploymentPlanTask enforceTask = new UpdateDeploymentPlanTask();
            enforceTask.setConsumerId(orchestratorId);
            enforceTask.setDeploymentPlan(state.getDeploymentPlan());
            addNewTask(newTasks, enforceTask);

            state.setDeploymentPlanningRequired(false);
        }
        return newTasks;
    }

    private ServiceGridDeploymentPlan updateDeploymentPlan() {

        ServiceGridDeploymentPlan deploymentPlan = state.getDeploymentPlan();

        for (final ServiceConfig newServiceConfig : state.getCapacityPlan().getServices()) {

            final ServiceDeploymentPlan oldServicePlan = deploymentPlan.getServiceById(newServiceConfig.getServiceId());
            deploymentPlanUpdateService(deploymentPlan, oldServicePlan, newServiceConfig);

            final URI serviceId = newServiceConfig.getServiceId();
            final ServiceConfig oldServiceConfig = oldServicePlan == null ? null : oldServicePlan.getServiceConfig();
            int oldNumberOfInstances = oldServiceConfig == null ? 0 : oldServiceConfig.getPlannedNumberOfInstances();
            int newNumberOfInstances = newServiceConfig.getPlannedNumberOfInstances();
            if (newNumberOfInstances > oldNumberOfInstances) {
                for (int i = newNumberOfInstances - oldNumberOfInstances; i > 0; i--) {

                    final URI instanceId = newInstanceId(serviceId);
                    final URI agentId = newAgentId();
                    ServiceInstanceDeploymentPlan instancePlan = new ServiceInstanceDeploymentPlan();
                    instancePlan.setAgentId(agentId);
                    instancePlan.setInstanceId(instanceId);
                    instancePlan.setDesiredLifecycle(newServiceConfig.getInstanceLifecycleStateMachine().getFinalInstanceLifecycle());
                    deploymentPlan.addServiceInstance(serviceId, instancePlan);
                }
            } else if (newNumberOfInstances < oldNumberOfInstances) {
                for (int i = oldNumberOfInstances - newNumberOfInstances; i > 0; i--) {
                    final int index = state.getAndDecrementNextServiceInstanceIndex(serviceId);
                    final URI instanceId = ServiceUtils.newInstanceId(serviceId, index);
                    boolean removed = deploymentPlan.removeServiceInstance(instanceId);
                    Preconditions.checkState(removed);
                }
            }
        }

        final Function<Object, URI> getServiceIdFunc = new Function<Object, URI>() {

            @Override
            public URI apply(Object serviceConfig) {
                if (serviceConfig instanceof ServiceConfig) {
                    return ((ServiceConfig) serviceConfig).getServiceId();
                }
                if (serviceConfig instanceof ServiceDeploymentPlan) {
                    return ((ServiceDeploymentPlan) serviceConfig).getServiceConfig().getServiceId();
                }
                Preconditions.checkArgument(false, "Unsupported type " + serviceConfig.getClass());
                return null;
            }
        };

        Set<URI> plannedServiceIds =
                Sets.newHashSet(Iterables.transform(state.getDeploymentPlan().getServices(), getServiceIdFunc));
        Set<URI> installedServiceIds =
                Sets.newHashSet(Iterables.transform(state.getCapacityPlan().getServices(), getServiceIdFunc));
        Set<URI> uninstalledServiceIds =
                Sets.difference(plannedServiceIds, installedServiceIds);

        for (URI uninstalledServiceId : uninstalledServiceIds) {
            state.getDeploymentPlan().removeService(uninstalledServiceId);
        }
        return deploymentPlan;
    }

    private void deploymentPlanUpdateService(
            ServiceGridDeploymentPlan deploymentPlan,
            ServiceDeploymentPlan oldServicePlan,
            ServiceConfig newServiceConfig) {

        final ServiceDeploymentPlan newServicePlan = new ServiceDeploymentPlan();
        newServicePlan.setServiceConfig(StreamUtils.cloneElement(mapper, newServiceConfig));
        if (oldServicePlan == null) {
            deploymentPlan.addService(newServicePlan);
        } else if (!StreamUtils.elementEquals(mapper, newServiceConfig, oldServicePlan.getServiceConfig())) {
            newServicePlan.setInstances(oldServicePlan.getInstances());
            deploymentPlan.replaceServiceById(oldServicePlan.getServiceConfig().getServiceId(), newServicePlan);
        }
    }

    private boolean isServiceInstalled(final URI serviceId) {
        return state.getCapacityPlan().getServiceById(serviceId) != null;
    }

    private URI newInstanceId(URI serviceId) {
        final int index = state.getAndIncrementNextServiceInstanceIndex(serviceId);
        return ServiceUtils.newInstanceId(serviceId, index);
    }

    private URI newAgentId() {
        return ServiceUtils.newAgentId(agentsId, state.getAndIncrementNextAgentIndex());
    }

    @TaskConsumerStateHolder
    public TaskConsumerState getState() {
        return state;
    }

    private static void addNewTask(List<Task> newTasks, final Task task) {

        newTasks.add(task);
    }


    private void checkServiceId(final URI serviceId) {
        Preconditions.checkArgument(serviceId.toString().endsWith("/"), "%s must end with /", serviceId);
    }
}
