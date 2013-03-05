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

import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerState;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskProducer;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlannerState;
import org.cloudifysource.cosmo.service.tasks.InstallServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScaleServiceTask;
import org.cloudifysource.cosmo.service.tasks.UninstallServiceTask;

import java.net.URI;
import java.util.List;

import static org.cloudifysource.cosmo.service.tasks.UpdateDeploymentCommandlineTask.cli;
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

    public ServiceGridDeploymentPlanner(ServiceGridDeploymentPlannerParameter parameterObject) {
        this.orchestratorId = parameterObject.getOrchestratorId();
        this.state = new ServiceGridDeploymentPlannerState();
        this.state.setTasksHistory(ServiceUtils.toTasksHistoryId(parameterObject.getDeploymentPlannerId()));
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
        state.addService(serviceConfig);
        state.setOrchestratorUpdateRequired(true);
    }

    @TaskConsumer(persistTask = true)
    public void uninstallService(final UninstallServiceTask task) {
        URI serviceId = task.getServiceId();
        checkServiceId(serviceId);
        boolean installed = isServiceInstalled(serviceId);
        Preconditions.checkState(installed);
        state.removeService(serviceId);
        state.setOrchestratorUpdateRequired(true);
    }

    @TaskProducer
    public Iterable<Task> deploymentPlan() {

        List<Task> newTasks = Lists.newArrayList();
        if (state.isOrchestratorUpdateRequired()) {
            updateOrchestratorWithPlan(newTasks);
            state.setOrchestratorUpdateRequired(false);
        }
        return newTasks;
    }

    private void updateOrchestratorWithPlan(List<Task> newTasks) {

        for (final ServiceConfig serviceConfig : state.getCapacityPlan().getServices()) {

            final String serviceName = serviceConfig.getDisplayName();
            final String prefix = serviceName + "_";
            final String aliasGroup = getAliasGroup(serviceConfig);

            final Task planSetTask = cli(aliasGroup, "plan_set", serviceName,
                    "--instances", String.valueOf(serviceConfig.getPlannedNumberOfInstances()),
                    "--min_instances", String.valueOf(serviceConfig.getMinNumberOfInstances()),
                    "--max_instances", String.valueOf(serviceConfig.getMaxNumberOfInstances()));
            addNewTask(newTasks, planSetTask);

            for (int i = 1; i <= serviceConfig.getMaxNumberOfInstances(); i++) {
                final String alias = aliasGroup  + i;
                final Task lifecycleTask = cli(alias, "lifecycle_set", serviceName,
                    prefix + "cleaned<-->" + prefix + "installed<-->" + prefix + "configured->" + prefix + "started" +
                            "," + prefix + "started->" + prefix + "stopped->" + prefix + "cleaned",
                    "--begin", prefix + "cleaned",
                    "--end", prefix + "started");
                addNewTask(newTasks, lifecycleTask);

                if (i <= serviceConfig.getPlannedNumberOfInstances()) {
                    final Task instanceStartedTask = cli(alias, prefix + "started");
                    addNewTask(newTasks, instanceStartedTask);

                    final Task cloudmachineReachableTask = cli(alias, "cloudmachine_reachable");
                    addNewTask(newTasks, cloudmachineReachableTask);

                } else {
                    final Task instanceCleanedTask = cli(alias, prefix + "cleaned");
                    addNewTask(newTasks, instanceCleanedTask);

                    final Task cloudmachineTerminatedTask = cli(alias, "cloudmachine_terminated");
                    addNewTask(newTasks, cloudmachineTerminatedTask);
                }
            }
        }

        for (ServiceConfig serviceConfig : state.getCapacityPlan().getRemovedServices()) {

            final String serviceName = serviceConfig.getDisplayName();
            final String aliasGroup = getAliasGroup(serviceConfig);
            final Task planUnsetTask = cli(aliasGroup, "plan_unset", serviceName);
            addNewTask(newTasks, planUnsetTask);
            final String prefix = serviceName + "_";

            for (int i = 1; i <= serviceConfig.getMaxNumberOfInstances(); i++) {
                final String alias = aliasGroup  + i;
                final Task instanceCleanedTask = cli(alias, prefix + "cleaned");
                addNewTask(newTasks, instanceCleanedTask);

                final Task cloudmachineTerminatedTask = cli(alias, "cloudmachine_terminated");
                addNewTask(newTasks, cloudmachineTerminatedTask);
            }
        }
    }

    /**
     * Have a different alias not related to service serviceName, since alias can have more than one service.
     */
    private String getAliasGroup(ServiceConfig serviceConfig) {
        String aliasGroup = serviceConfig.getAliasGroup();
        if (!aliasGroup.endsWith("/")) {
            aliasGroup += "/";
        }
        return aliasGroup;
    }

    private boolean isServiceInstalled(final URI serviceId) {
        return state.getCapacityPlan().getServiceById(serviceId) != null;
    }


    @TaskConsumerStateHolder
    public TaskConsumerState getState() {
        return state;
    }

    private void addNewTask(List<Task> newTasks, final Task task) {
        task.setConsumerId(orchestratorId);
        newTasks.add(task);
    }


    private void checkServiceId(final URI serviceId) {
        Preconditions.checkArgument(serviceId.toString().endsWith("/"), "%s must end with /", serviceId);
    }
}
