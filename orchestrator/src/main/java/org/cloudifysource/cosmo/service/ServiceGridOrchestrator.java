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

import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.ImpersonatingTaskConsumer;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.TaskProducer;
import org.cloudifysource.cosmo.agent.health.AgentHealthProbe;
import org.cloudifysource.cosmo.agent.health.AgentPingHealth;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.MachineLifecycleTask;
import org.cloudifysource.cosmo.agent.tasks.PlanAgentTask;
import org.cloudifysource.cosmo.service.id.AliasGroupId;
import org.cloudifysource.cosmo.service.id.AliasId;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachineText;
import org.cloudifysource.cosmo.service.state.AgentPlan;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridOrchestratorState;
import org.cloudifysource.cosmo.service.state.ServiceInstanceDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.service.tasks.PlanServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.PlanServiceTask;
import org.cloudifysource.cosmo.service.tasks.RecoverServiceInstanceStateTask;
import org.cloudifysource.cosmo.service.tasks.RemoveServiceInstanceFromAgentTask;
import org.cloudifysource.cosmo.service.tasks.RemoveServiceInstanceFromServiceTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstalledTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstallingTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.ServiceUninstalledTask;
import org.cloudifysource.cosmo.service.tasks.ServiceUninstallingTask;
import org.cloudifysource.cosmo.service.tasks.UnreachableServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.UpdateDeploymentCommandlineTask;
import org.cloudifysource.cosmo.state.StateReader;

import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Consumes task from the planner, and orchestrates their execution
 * by producing tasks to agents and machine provisioning.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridOrchestrator {

    private final ServiceGridOrchestratorState state;

    private final URI machineProvisionerId;
    private final URI orchestratorId;
    private final StateReader stateReader;
    private final AgentHealthProbe agentHealthProbe;

    public ServiceGridOrchestrator(ServiceGridOrchestratorParameter parameterObject) {
        Preconditions.checkNotNull(parameterObject);
        Preconditions.checkNotNull(parameterObject.getOrchestratorId());
        this.orchestratorId = parameterObject.getOrchestratorId();
        Preconditions.checkNotNull(parameterObject.getMachineProvisionerId());
        this.machineProvisionerId = parameterObject.getMachineProvisionerId();
        Preconditions.checkNotNull(parameterObject.getStateReader());
        this.stateReader = parameterObject.getStateReader();
        Preconditions.checkNotNull(parameterObject.getAgentHealthProbe());
        this.agentHealthProbe = parameterObject.getAgentHealthProbe();
        this.state = new ServiceGridOrchestratorState();
        Preconditions.checkNotNull(parameterObject.getServerId());
        this.state.setServerId(parameterObject.getServerId());
        this.state.setTasksHistory(ServiceUtils.toTasksHistoryId(orchestratorId));
    }

    @TaskProducer
    public Iterable<Task> orchestrate() {

        final List<Task> newTasks = Lists.newArrayList();

        agentHealthProbe.monitorAgents(getPlannedAgentIds());
        final Map<URI, AgentPingHealth> agentsHealthStatus = agentHealthProbe.getAgentsHealthStatus();

        boolean ready = syncStateWithDeploymentPlan(newTasks, agentsHealthStatus);

        if (ready) {
            //start orchestrating according to current state

            for (final URI agentId : getPlannedAgentIds()) {
                orchestrateAgent(newTasks, agentId, agentsHealthStatus.get(agentId));
            }

            final ServiceGridDeploymentPlan deploymentPlan = state.getDeploymentPlan();
            for (final ServiceInstanceDeploymentPlan instancePlan : deploymentPlan.getInstances()) {
                orchestrateServiceInstance(newTasks, instancePlan);
            }

            for (final URI serviceId : ImmutableSet.copyOf(getPlannedServiceIds())) {

                Optional<ServiceDeploymentPlan> servicePlan = deploymentPlan.getServicePlan(serviceId);
                final boolean serviceAutoUninstall =
                        servicePlan.isPresent() &&
                        servicePlan.get().isAutoUninstall();

                if (serviceAutoUninstall &&
                    Iterables.isEmpty(deploymentPlan.getInstanceIdsByServiceId(serviceId)) &&
                    Iterables.isEmpty(getServiceState(serviceId).getInstanceIds())) {

                    uninstallService(serviceId);
                }
            }

            for (final URI serviceId : Iterables.concat(getPlannedServiceIds(), state.getServiceIdsToUninstall())) {
                orchestrateService(newTasks, serviceId);
            }
        }

        return newTasks;
    }

    @TaskConsumer
    public void updateDeployment(UpdateDeploymentCommandlineTask task) {
        final String command = task.getArguments().get(1);
        if (command.equals("plan_set")) {
            final LifecycleName name = new LifecycleName(task.getArguments().get(2));
            final AliasGroupId aliasGroup = new AliasGroupId(task.getArguments().get(0));
            final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), aliasGroup, name);
            final ServiceConfig serviceConfig = new ServiceConfig();
            serviceConfig.setPlannedNumberOfInstances(Integer.valueOf(task.getOptions().get("instances")));
            serviceConfig.setMaxNumberOfInstances(Integer.valueOf(task.getOptions().get("max_instances")));
            serviceConfig.setMinNumberOfInstances(Integer.valueOf(task.getOptions().get("min_instances")));
            serviceConfig.setServiceId(serviceId);
            serviceConfig.setDisplayName(name.getName());
            final ServiceDeploymentPlan servicePlan = new ServiceDeploymentPlan();
            servicePlan.setServiceConfig(serviceConfig);
            servicePlan.setAutoUninstall(false);
            state.getDeploymentPlan().setService(servicePlan);

        } else if (command.equals("plan_unset")) {
            final AliasGroupId aliasGroup = new AliasGroupId(task.getArguments().get(0));
            final LifecycleName name = new LifecycleName(task.getArguments().get(2));
            final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), aliasGroup, name);
            uninstallService(serviceId);

        } else if (command.equals("lifecycle_set")) {
            final AliasId alias = new AliasId(task.getArguments().get(0));
            final LifecycleName name = new LifecycleName(task.getArguments().get(2));
            final LifecycleStateMachineText text = new LifecycleStateMachineText(task.getArguments().get(3));
            final LifecycleState begin = new LifecycleState(task.getOptions().get("begin"));
            final LifecycleState end = new LifecycleState(task.getOptions().get("end"));
            LifecycleStateMachine stateMachine = new LifecycleStateMachine();
            stateMachine.setName(name);
            stateMachine.setText(text);
            stateMachine.setBeginState(begin);
            stateMachine.setEndState(end);

            final URI instanceId = ServiceUtils.newInstanceId(state.getServerId(), alias, name);
            final URI agentId = ServiceUtils.newAgentId(state.getServerId(), alias);
            final AliasGroupId aliasGroup = alias.getAliasGroup();
            final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), aliasGroup, name);
            final ServiceInstanceDeploymentPlan instancePlan = new ServiceInstanceDeploymentPlan();
            instancePlan.setInstanceId(instanceId);
            instancePlan.setAgentId(agentId);
            instancePlan.setStateMachine(stateMachine);
            instancePlan.setServiceId(serviceId);
            state.getDeploymentPlan().addServiceInstance(instancePlan);

        } else if (command.startsWith("cloudmachine_")) {
            final AliasId alias = new AliasId(task.getArguments().get(0));
            final URI agentId = ServiceUtils.newAgentId(state.getServerId(), alias);
            final Optional<AgentPlan> agentPlan = state.getDeploymentPlan().getAgentPlan(agentId);
            if (agentPlan.isPresent()) {
                agentPlan.get().setLifecycleState(new LifecycleState(command));

            } else {
                final AgentPlan newAgentPlan = new AgentPlan();
                newAgentPlan.setAgentId(agentId);
                newAgentPlan.setLifecycleState(new LifecycleState(command));
                state.getDeploymentPlan().addAgent(newAgentPlan);
            }

        } else if (command.equals("machine_set")) {
            AliasId alias = new AliasId(task.getArguments().get(0));
            final URI agentId = ServiceUtils.newAgentId(state.getServerId(), alias);
            Optional<AgentPlan> agentPlan = state.getDeploymentPlan().getAgentPlan(agentId);
            if (!agentPlan.isPresent()) {
                final AgentPlan newAgentPlan = new AgentPlan();
                newAgentPlan.setAgentId(agentId);
                //TODO: We are simulating here a cloudmachine lifecycle
                //we need to define a statemachine that is suitable for a data center machine.
                newAgentPlan.setLifecycleState(new LifecycleState("cloudmachine_reachable"));
                state.getDeploymentPlan().addAgent(newAgentPlan);
                agentPlan = Optional.fromNullable(newAgentPlan);
            }
            agentPlan.get().setHost(task.getOptions().get("ip"));
            agentPlan.get().setKeyFile(task.getOptions().get("keyfile"));
            agentPlan.get().setUserName(task.getOptions().get("username"));

        } else if (command.equals("machine_unset")) {
            AliasId alias = new AliasId(task.getArguments().get(0));
            final URI agentId = ServiceUtils.newAgentId(state.getServerId(), alias);
            Optional<AgentPlan> agentPlan = state.getDeploymentPlan().getAgentPlan(agentId);
            if (agentPlan.isPresent()) {
                agentPlan.get().setLifecycleState(new LifecycleState("cloudmachine_terminated"));
            }

        } else {
            final AliasId alias = new AliasId(task.getArguments().get(0));
            final LifecycleState desiredState = new LifecycleState(command);
            final LifecycleName name = LifecycleName.fromLifecycleState(desiredState);
            final URI instanceId = ServiceUtils.newInstanceId(state.getServerId(), alias, name);
            final LifecycleStateMachine stateMachine =
                    state.getDeploymentPlan().getInstancePlan(instanceId).get()
                         .getStateMachine();
            stateMachine.getProperties().putAll(task.getOptions());
            stateMachine.setCurrentState(desiredState);

            if (!state.getDeploymentPlan().getServiceByInstanceId(instanceId).isPresent()) {
                // create default ServiceConfig
                final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), alias.getAliasGroup(), name);
                final ServiceConfig serviceConfig = new ServiceConfig();
                serviceConfig.setServiceId(serviceId);
                serviceConfig.setDisplayName(name.getName());
                final ServiceDeploymentPlan servicePlan = new ServiceDeploymentPlan();
                servicePlan.setAutoUninstall(true);
                servicePlan.setServiceConfig(serviceConfig);
                state.getDeploymentPlan().setService(servicePlan);
            }
        }
    }

    @ImpersonatingTaskConsumer
    public void planAgent(PlanAgentTask task,
                          TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {

        final int numberOfMachineRestarts = 0;

        final URI agentId = task.getStateId();
        Optional<AgentPlan> agentPlan = state.getDeploymentPlan().getAgentPlan(agentId);
        Preconditions.checkState(agentPlan.isPresent());

        AgentState agentState = new AgentState();
        agentState.setNumberOfMachineStarts(numberOfMachineRestarts);
        agentState.setTasksHistory(ServiceUtils.toTasksHistoryId(task.getStateId()));
        agentState.setHost(agentPlan.get().getHost());
        agentState.setUserName(agentPlan.get().getUserName());
        agentState.setKeyFile(agentPlan.get().getKeyFile());
        impersonatedStateModifier.put(agentState);
    }

    @ImpersonatingTaskConsumer
    public void planService(PlanServiceTask task,
                            TaskConsumerStateModifier<ServiceState> impersonatedStateModifier) {

        ServiceState serviceState = impersonatedStateModifier.get();
        if (serviceState == null) {
            serviceState = new ServiceState();
        }
        serviceState.setServiceConfig(task.getServiceConfig());
        serviceState.setInstanceIds(task.getServiceInstanceIds());
        serviceState.setProgress(ServiceState.Progress.INSTALLING_SERVICE);
        serviceState.setTasksHistory(ServiceUtils.toTasksHistoryId(task.getStateId()));
        impersonatedStateModifier.put(serviceState);
    }

    @ImpersonatingTaskConsumer
    public void serviceUninstalling(ServiceUninstallingTask task,
                                    TaskConsumerStateModifier<ServiceState> impersonatedStateModifier) {
        ServiceState serviceState = impersonatedStateModifier.get();
        serviceState.setProgress(ServiceState.Progress.UNINSTALLING_SERVICE);
        impersonatedStateModifier.put(serviceState);
    }

    @ImpersonatingTaskConsumer
    public void serviceInstalling(ServiceInstallingTask task,
                                  TaskConsumerStateModifier<ServiceState> impersonatedStateModifier) {
        ServiceState serviceState = impersonatedStateModifier.get();
        serviceState.setProgress(ServiceState.Progress.INSTALLING_SERVICE);
        impersonatedStateModifier.put(serviceState);
    }

    @ImpersonatingTaskConsumer
    public void serviceUninstalled(ServiceUninstalledTask task,
                                   TaskConsumerStateModifier<ServiceState> impersonatedStateModifier) {
        ServiceState serviceState = impersonatedStateModifier.get();
        serviceState.setProgress(ServiceState.Progress.SERVICE_UNINSTALLED);
        impersonatedStateModifier.put(serviceState);

        final URI serviceId = serviceState.getServiceConfig().getServiceId();
        state.removeServiceIdToUninstall(serviceId);
    }

    @ImpersonatingTaskConsumer
    public void planServiceInstance(PlanServiceInstanceTask task,
                                    TaskConsumerStateModifier impersonatedStateModifier) {
        ServiceInstanceState instanceState = new ServiceInstanceState();
        instanceState.setAgentId(task.getAgentId());
        instanceState.setServiceId(task.getServiceId());
        final LifecycleStateMachine stateMachine = task.getStateMachine();
        Preconditions.checkNotNull(stateMachine.getBeginState());
        Preconditions.checkNotNull(stateMachine.getEndState());
        stateMachine.setCurrentState(stateMachine.getBeginState());
        instanceState.setStateMachine(stateMachine);
        instanceState.setTasksHistory(ServiceUtils.toTasksHistoryId(task.getStateId()));
        instanceState.setStateMachine(stateMachine);
        impersonatedStateModifier.put(instanceState);
    }

    @ImpersonatingTaskConsumer
    public void unreachableServiceInstance(
            final UnreachableServiceInstanceTask task,
            final TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
        ServiceInstanceState instanceState = impersonatedStateModifier.get();
        instanceState.setReachable(false);
        impersonatedStateModifier.put(instanceState);
    }

    @ImpersonatingTaskConsumer
    public void removeServiceInstanceFromService(
            final RemoveServiceInstanceFromServiceTask task,
            final TaskConsumerStateModifier<ServiceState> impersonatedStateModifier) {

        final ServiceState serviceState = impersonatedStateModifier.get();
        serviceState.removeInstance(task.getInstanceId());
        impersonatedStateModifier.put(serviceState);
    }

    @ImpersonatingTaskConsumer
    public void serviceInstalled(final ServiceInstalledTask task,
                                 final TaskConsumerStateModifier<ServiceState> impersonatedStateModifier) {
        ServiceState serviceState = impersonatedStateModifier.get();
        serviceState.setProgress(ServiceState.Progress.SERVICE_INSTALLED);
        impersonatedStateModifier.put(serviceState);
    }

    @ImpersonatingTaskConsumer
    public void removeServiceInstanceFromAgent(final RemoveServiceInstanceFromAgentTask task,
                                               final TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {

        final AgentState agentState = impersonatedStateModifier.get();
        agentState.removeServiceInstanceId(task.getInstanceId());
        impersonatedStateModifier.put(agentState);
    }

    private boolean syncStateWithDeploymentPlan(
            final List<Task> newTasks,
            final Map<URI, AgentPingHealth> agentsHealthStatus) {

        boolean syncComplete = true;

        for (final URI agentId : getPlannedAgentIds()) {
            final AgentPingHealth pingHealth = agentsHealthStatus.get(agentId);
            Preconditions.checkNotNull(pingHealth);
            final AgentState agentState = getAgentState(agentId);

            if (pingHealth == AgentPingHealth.AGENT_REACHABLE) {
                Preconditions.checkState(agentState != null, "Responding agent cannot have null state");
                if (!agentState.isMachineReachableLifecycle()) {
                    syncComplete = false;

                } else {
                    Iterable<URI> plannedInstanceIds = state.getDeploymentPlan().getInstanceIdsByAgentId(agentId);
                    for (URI instanceId : plannedInstanceIds) {
                        ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
                        if (instanceState == null || !instanceState.isReachable()) {

                            syncComplete = false;
                            final URI serviceId = state.getDeploymentPlan().getServiceIdByInstanceId(instanceId).get();
                            final ServiceState serviceState = getServiceState(serviceId);
                            final RecoverServiceInstanceStateTask recoverInstanceStateTask =
                                    new RecoverServiceInstanceStateTask();
                            recoverInstanceStateTask.setStateId(instanceId);
                            recoverInstanceStateTask.setConsumerId(agentId);
                            recoverInstanceStateTask.setServiceId(serviceId);
                            recoverInstanceStateTask.setStateMachine(
                                    state.getDeploymentPlan().getInstancePlan(instanceId).get().getStateMachine());
                            addNewTaskIfNotExists(newTasks, recoverInstanceStateTask);
                        }
                    }
                }
            } else if (pingHealth == AgentPingHealth.AGENT_UNREACHABLE) {

                if (agentState == null) {
                    syncComplete = false;
                    final PlanAgentTask planAgentTask = new PlanAgentTask();
                    planAgentTask.setStateId(agentId);
                    planAgentTask.setConsumerId(orchestratorId);
                    addNewTaskIfNotExists(newTasks, planAgentTask);
                }

                Iterable<URI> plannedInstanceIds = state.getDeploymentPlan().getInstanceIdsByAgentId(agentId);
                for (URI instanceId : plannedInstanceIds) {
                    if (getServiceInstanceState(instanceId) == null) {
                        syncComplete = false;
                        final URI serviceId =
                                state.getDeploymentPlan().getServiceIdByInstanceId(instanceId).get();
                        final LifecycleStateMachine stateMachine =
                            state.getDeploymentPlan().getInstancePlan(instanceId).get().getStateMachine();
                        Preconditions.checkNotNull(stateMachine.getBeginState());
                        Preconditions.checkNotNull(stateMachine.getEndState());
                        final PlanServiceInstanceTask planInstanceTask = new PlanServiceInstanceTask();
                        planInstanceTask.setStateId(instanceId);
                        planInstanceTask.setAgentId(agentId);
                        planInstanceTask.setServiceId(serviceId);
                        planInstanceTask.setConsumerId(orchestratorId);
                        planInstanceTask.setStateMachine(stateMachine);
                        addNewTaskIfNotExists(newTasks, planInstanceTask);
                    }
                }
            } else {
                Preconditions.checkState(pingHealth == AgentPingHealth.UNDETERMINED);
                syncComplete = false;
                //better luck next time. wait until agent health is determined.
            }
        }

        for (final ServiceDeploymentPlan servicePlan : state.getDeploymentPlan().getServices()) {
            final URI serviceId = servicePlan.getServiceConfig().getServiceId();
            final ServiceState serviceState = getServiceState(serviceId);
            final Iterable<URI> plannedInstanceIds = state.getDeploymentPlan().getInstanceIdsByServiceId(serviceId);
            Iterable<URI> actualInstanceIds =
                    (serviceState == null ? Lists.<URI>newArrayList() : serviceState.getInstanceIds());
            final Iterable<URI> allInstanceIds =
                    ImmutableSet.copyOf(Iterables.concat(actualInstanceIds, plannedInstanceIds));
            if (serviceState == null ||
                !Iterables.elementsEqual(actualInstanceIds, allInstanceIds)) {

                syncComplete = false;
                final PlanServiceTask planServiceTask = new PlanServiceTask();
                planServiceTask.setStateId(serviceId);
                planServiceTask.setConsumerId(orchestratorId);
                // when scaling out, the service state should include the new planned instances.
                // when scaling in,  the service state should still include the old instances until they are removed.
                planServiceTask.setServiceInstanceIds(Lists.newArrayList(allInstanceIds));
                planServiceTask.setServiceConfig(servicePlan.getServiceConfig());
                addNewTaskIfNotExists(newTasks, planServiceTask);
            }
        }

        return syncComplete;
    }

    private Iterable<URI> getPlannedAgentIds() {
        return state.getDeploymentPlan().getAgentIds();
    }

    private void orchestrateService(List<Task> newTasks, URI serviceId) {

        final ServiceState serviceState = getServiceState(serviceId);
        final Predicate<URI> findInstanceNotStartedPredicate = new Predicate<URI>() {

            @Override
            public boolean apply(final URI instanceId) {
                return !getServiceInstanceState(instanceId).getStateMachine().isLifecycleEndState();
            }
        };

        Set<URI> serviceIdsToUninstall = state.getServiceIdsToUninstall();
        if (serviceIdsToUninstall.contains(serviceId) &&
            serviceState.isProgress(
                ServiceState.Progress.INSTALLING_SERVICE,
                ServiceState.Progress.SERVICE_INSTALLED)) {
            ServiceUninstallingTask task = new ServiceUninstallingTask();
            task.setStateId(serviceId);
            task.setConsumerId(orchestratorId);
            addNewTaskIfNotExists(newTasks, task);
        } else if (serviceState.isProgress(ServiceState.Progress.INSTALLING_SERVICE)) {
            final boolean isServiceInstalling =
                    Iterables.any(serviceState.getInstanceIds(), findInstanceNotStartedPredicate);
            if (!isServiceInstalling) {
                ServiceInstalledTask task = new ServiceInstalledTask();
                task.setConsumerId(orchestratorId);
                task.setStateId(serviceId);
                addNewTaskIfNotExists(newTasks, task);
            }
        } else if (serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED)) {
            final boolean isServiceInstalling =
                    Iterables.tryFind(serviceState.getInstanceIds(), findInstanceNotStartedPredicate)
                            .isPresent();
            if (isServiceInstalling) {
                ServiceInstallingTask task = new ServiceInstallingTask();
                task.setConsumerId(orchestratorId);
                task.setStateId(serviceId);
                addNewTaskIfNotExists(newTasks, task);
            }
        } else if (serviceState.isProgress(ServiceState.Progress.UNINSTALLING_SERVICE)) {
            if (serviceState.getInstanceIds().isEmpty()) {
                ServiceUninstalledTask task = new ServiceUninstalledTask();
                task.setConsumerId(orchestratorId);
                task.setStateId(serviceId);
                addNewTaskIfNotExists(newTasks, task);
            }
        } else if (serviceState.isProgress(ServiceState.Progress.SERVICE_UNINSTALLED)) {
            // do nothing
        } else {
            Preconditions.checkState(false, "Unknown service state" + serviceState.getProgress());
        }
    }

    private void uninstallService(URI serviceId) {
        state.getDeploymentPlan().removeService(serviceId);
        state.addServiceIdToUninstall(serviceId);
    }

    private void orchestrateServiceInstance(List<Task> newTasks, ServiceInstanceDeploymentPlan instancePlan) {
        final URI instanceId = instancePlan.getInstanceId();
        final URI agentId = state.getDeploymentPlan().getAgentIdByInstanceId(instanceId);
        final AgentState agentState = getAgentState(agentId);
        final ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
        final LifecycleStateMachine stateMachine = instanceState.getStateMachine();
        final LifecycleState desiredLifecycle = instancePlan.getStateMachine().getCurrentState();
        final LifecycleState nextLifecycle = stateMachine.getNextLifecycleState(desiredLifecycle);

        //follow the machine lifecycle as it is being started
        if (!agentState.isMachineReachableLifecycle() && instanceState.isReachable()) {
            final UnreachableServiceInstanceTask
                    unreachableInstanceTask = new UnreachableServiceInstanceTask();
            unreachableInstanceTask.setConsumerId(orchestratorId);
            unreachableInstanceTask.setStateId(instanceId);
            addNewTaskIfNotExists(newTasks, unreachableInstanceTask);

        } else if (desiredLifecycle.equals(stateMachine.getBeginState()) && // == 'service_cleaned'
            (stateMachine.isLifecycleState(desiredLifecycle) ||
             !instanceState.isReachable())) {

            // remove instance from agent
            if (agentState.getServiceInstanceIds().contains(instanceId)) {
                RemoveServiceInstanceFromAgentTask removeFromAgentTask = new RemoveServiceInstanceFromAgentTask();
                if (agentState.isMachineReachableLifecycle()) {
                    removeFromAgentTask.setConsumerId(agentId);
                } else {
                    removeFromAgentTask.setConsumerId(orchestratorId);
                    removeFromAgentTask.setConsumerId(orchestratorId);
                }
                removeFromAgentTask.setStateId(agentId);
                removeFromAgentTask.setInstanceId(instanceId);
                addNewTaskIfNotExists(newTasks, removeFromAgentTask);
            }

            final URI serviceId = instancePlan.getServiceId();
            final ServiceState serviceState = getServiceState(serviceId);
            // remove instance from service
            if (serviceState.getInstanceIds().contains(instanceId)) {
                final RemoveServiceInstanceFromServiceTask task = new RemoveServiceInstanceFromServiceTask();
                task.setConsumerId(orchestratorId);
                task.setStateId(serviceId);
                task.setInstanceId(instanceId);
                addNewTaskIfNotExists(newTasks, task);
            }

        } else if (agentState.isMachineReachableLifecycle() && instanceState.isReachable()) {
            if (!stateMachine.isLifecycleState(nextLifecycle)) {
                //step to the next lifecycle state
                final ServiceInstanceTask task = new ServiceInstanceTask();
                task.setLifecycleState(nextLifecycle);
                task.setStateId(instanceId);
                task.setConsumerId(instanceState.getAgentId());
                addNewTaskIfNotExists(newTasks, task);
            } else {
                // do nothing, we're done
            }
        }
    }

    private ServiceState getServiceState(final URI serviceId) {
        return ServiceUtils.getServiceState(stateReader, serviceId);
    }

    private ServiceInstanceState getServiceInstanceState(URI instanceId) {
        return ServiceUtils.getServiceInstanceState(stateReader, instanceId);
    }


    private void orchestrateAgent(List<Task> newTasks, URI agentId, AgentPingHealth agentHealthStatus) {

        final AgentState agentState = getAgentState(agentId);
        final LifecycleState desiredLifecycle =
                state.getDeploymentPlan().getAgentPlan(agentId).get().getLifecycleState();

        if (agentState.isMachineReachableLifecycle() &&
            agentHealthStatus == AgentPingHealth.AGENT_UNREACHABLE) {

            final MachineLifecycleTask task = new MachineLifecycleTask();
            task.setLifecycleState(agentState.getMachineUnreachableLifecycle());
            task.setStateId(agentId);
            task.setConsumerId(machineProvisionerId);
            addNewTaskIfNotExists(newTasks, task);
        } else if (!agentState.getStateMachine().isLifecycleState(desiredLifecycle)) {
            final LifecycleState nextAgentLifecycle =
                    agentState.getStateMachine().getNextLifecycleState(desiredLifecycle);
            Preconditions.checkNotNull(nextAgentLifecycle);
            if (isAllInstancesRemovedOrUnreachable(agentState) &&
                !agentState.getStateMachine().isLifecycleState(nextAgentLifecycle)) {
                final MachineLifecycleTask task = new MachineLifecycleTask();
                task.setLifecycleState(nextAgentLifecycle);
                task.setStateId(agentId);
                task.setConsumerId(machineProvisionerId);
                addNewTaskIfNotExists(newTasks, task);
            }
        }
    }

    private boolean isAllInstancesRemovedOrUnreachable(final AgentState agentState) {
        final Iterable<URI> instanceIds = agentState.getServiceInstanceIds();
        return Iterables.all(instanceIds, new Predicate<URI>() {
            @Override
            public boolean apply(URI instanceId) {
                final ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
                return !instanceState.isReachable();
            }
        });
    }

    private AgentState getAgentState(URI agentId) {
        return ServiceUtils.getAgentState(stateReader, agentId);
    }

    /**
     * Adds a new task only if it has not been added recently.
     */
    public void addNewTaskIfNotExists(
            final List<Task> newTasks,
            final Task newTask) {

        addNewTask(newTasks, newTask);
    }

    private static void addNewTask(List<Task> newTasks, final Task task) {
        newTasks.add(task);
    }

    @TaskConsumerStateHolder
    public ServiceGridOrchestratorState getState() {
        return state;
    }

    private Iterable<URI> getPlannedServiceIds() {
        return state.getDeploymentPlan().getServiceIds();
    }

    /**
     * @return old ids that are not in the newIds, maintaining order, removing duplicates.
     */
    public static Iterable<URI> subtract(final Iterable<URI> oldIds, final Iterable<URI> newIds) {
        final Set<URI> idsToFilter = Sets.newHashSet(newIds);
        final Iterable<URI> diffWithDuplicates =
                Iterables.filter(oldIds, new Predicate<URI>() {

                    @Override
                    public boolean apply(URI id) {
                        return !idsToFilter.contains(id);
                    }
                });
        return ImmutableSet.copyOf(diffWithDuplicates);
    }
}
