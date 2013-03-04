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
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.TaskProducer;
import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.MachineLifecycleTask;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.agent.tasks.PlanAgentTask;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachineText;
import org.cloudifysource.cosmo.service.state.AgentPlan;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceDeploymentPlan;
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
import org.cloudifysource.cosmo.service.tasks.UnreachableServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.ServiceUninstalledTask;
import org.cloudifysource.cosmo.service.tasks.ServiceUninstallingTask;
import org.cloudifysource.cosmo.service.tasks.UpdateDeploymentCommandlineTask;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Consumes task from the planner, and orchestrates their execution
 * by producing tasks to agents and machine provisioning.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridOrchestrator {

    private static final long AGENT_UNREACHABLE_MILLISECONDS = TimeUnit.SECONDS.toMillis(30);

    private static final long AGENT_REACHABLE_RENEW_MILLISECONDS = AGENT_UNREACHABLE_MILLISECONDS / 2;

    private final ServiceGridOrchestratorState state;

    private final TaskReader taskReader;
    private final URI machineProvisionerId;
    private final URI orchestratorId;
    private final StateReader stateReader;

    private CurrentTimeProvider timeProvider;

    public ServiceGridOrchestrator(ServiceGridOrchestratorParameter parameterObject) {
        this.orchestratorId = parameterObject.getOrchestratorId();
        this.taskReader = parameterObject.getTaskReader();
        this.machineProvisionerId = parameterObject.getMachineProvisionerId();
        this.stateReader = parameterObject.getStateReader();
        this.timeProvider = parameterObject.getTimeProvider();
        this.state = new ServiceGridOrchestratorState();
        Preconditions.checkNotNull(parameterObject.getServerId());
        this.state.setServerId(parameterObject.getServerId());
        this.state.setTasksHistory(ServiceUtils.toTasksHistoryId(orchestratorId));
    }

    @TaskProducer
    public Iterable<Task> orchestrate() {

        final List<Task> newTasks = Lists.newArrayList();

        if (state.getDeploymentPlan() != null) {

            boolean ready = syncStateWithDeploymentPlan(newTasks);

            if (ready) {
                //start orchestrating according to current state
                final long nowTimestamp = timeProvider.currentTimeMillis();
                for (final URI agentId : getPlannedAgentIds()) {
                    orchestrateAgent(newTasks, nowTimestamp, agentId);
                }

                for (final ServiceInstanceDeploymentPlan instancePlan : state.getDeploymentPlan().getInstances()) {
                    orchestrateServiceInstance(newTasks, instancePlan);
                }

                for (final URI serviceId : Iterables.concat(getPlannedServiceIds(), state.getServiceIdsToUninstall())) {
                    orchestrateService(newTasks, serviceId);
                }
            }

            pingAgents(newTasks);
        }
        return newTasks;
    }

    @TaskConsumer
    public void updateDeployment(UpdateDeploymentCommandlineTask task) {
        final String command = task.getArguments().get(1);
        if (command.equals("plan_set")) {
            final LifecycleName name = new LifecycleName(task.getArguments().get(2));
            final String aliasGroup = task.getArguments().get(0);
            final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), aliasGroup, name);
            final ServiceConfig serviceConfig = new ServiceConfig();
            serviceConfig.setPlannedNumberOfInstances(Integer.valueOf(task.getOptions().get("instances")));
            serviceConfig.setMaxNumberOfInstances(Integer.valueOf(task.getOptions().get("max_instances")));
            serviceConfig.setMinNumberOfInstances(Integer.valueOf(task.getOptions().get("min_instances")));
            serviceConfig.setServiceId(serviceId);
            serviceConfig.setDisplayName(name.getName());
            final ServiceDeploymentPlan servicePlan = new ServiceDeploymentPlan();
            servicePlan.setServiceConfig(serviceConfig);
            state.getDeploymentPlan().setService(servicePlan);

        } else if (command.equals("plan_unset")) {
            final String aliasGroup = task.getArguments().get(0);
            final LifecycleName name = new LifecycleName(task.getArguments().get(2));
            final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), aliasGroup, name);
            state.getDeploymentPlan().removeService(serviceId);
            state.addServiceIdToUninstall(serviceId);

        } else if (command.equals("lifecycle_set")) {
            final String alias = task.getArguments().get(0);
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
            final String aliasGroup = ServiceUtils.toAliasGroup(alias);
            final URI serviceId = ServiceUtils.newServiceId(state.getServerId(), aliasGroup, name);
            final ServiceInstanceDeploymentPlan instancePlan = new ServiceInstanceDeploymentPlan();
            instancePlan.setInstanceId(instanceId);
            instancePlan.setAgentId(agentId);
            instancePlan.setStateMachine(stateMachine);
            instancePlan.setServiceId(serviceId);
            state.getDeploymentPlan().addServiceInstance(instancePlan);

        } else if (command.startsWith("cloudmachine_")) {
            final String alias = task.getArguments().get(0);
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

        } else {
            final String alias = task.getArguments().get(0);
            final LifecycleState desiredState = new LifecycleState(command);
            final LifecycleName name = LifecycleName.fromLifecycleState(desiredState);
            final URI instanceId = ServiceUtils.newInstanceId(state.getServerId(), alias, name);
            final LifecycleStateMachine stateMachine =
                    state.getDeploymentPlan().getInstancePlan(instanceId).get()
                         .getStateMachine();
            stateMachine.setCurrentState(desiredState);
        }
    }

    @ImpersonatingTaskConsumer
    public void planAgent(PlanAgentTask task,
                          TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {
        int numberOfMachineRestarts = 0;
        AgentState impersonatedAgentState = new AgentState();
        impersonatedAgentState.setServiceInstanceIds(task.getServiceInstanceIds());
        impersonatedAgentState.setNumberOfMachineStarts(numberOfMachineRestarts);
        impersonatedAgentState.setTasksHistory(ServiceUtils.toTasksHistoryId(task.getStateId()));
        impersonatedStateModifier.put(impersonatedAgentState);
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

    private boolean syncStateWithDeploymentPlan(final List<Task> newTasks) {
        boolean syncComplete = true;
        final long nowTimestamp = timeProvider.currentTimeMillis();
        for (final URI agentId : getPlannedAgentIds()) {
            AgentPingHealth pingHealth = getAgentPingHealth(agentId, nowTimestamp);
            AgentState agentState = getAgentState(agentId);
            boolean agentNotStarted =
                    (agentState == null || !agentState.isMachineReachableLifecycle());
            if (agentNotStarted &&
                state.isSyncedStateWithDeploymentBefore() &&
                pingHealth == AgentPingHealth.UNDETERMINED) {
                //If this agent were started, we would have resolved it as agent started in the previous sync
                //The agent probably never even started
                pingHealth = AgentPingHealth.AGENT_UNREACHABLE;
            }
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
                Iterable<URI> plannedInstanceIds = state.getDeploymentPlan().getInstanceIdsByAgentId(agentId);
                if (agentState == null) {
                    syncComplete = false;
                    final PlanAgentTask planAgentTask = new PlanAgentTask();
                    planAgentTask.setStateId(agentId);
                    planAgentTask.setConsumerId(orchestratorId);
                    planAgentTask.setServiceInstanceIds(Lists.newArrayList(plannedInstanceIds));
                    addNewTaskIfNotExists(newTasks, planAgentTask);
                }

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

        if (syncComplete) {
            state.setSyncedStateWithDeploymentBefore(true);
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

    /**
     * Ping all agents that are not doing anything.
     */
    private void pingAgents(List<Task> newTasks) {

        long nowTimestamp = timeProvider.currentTimeMillis();
        for (final URI agentId : getPlannedAgentIds()) {

            final AgentState agentState = getAgentState(agentId);

            AgentPingHealth agentPingHealth = getAgentPingHealth(agentId, nowTimestamp);
            if (agentPingHealth.equals(AgentPingHealth.AGENT_REACHABLE)) {
                final long taskTimestamp = agentState.getLastPingSourceTimestamp();
                final long sincePingMilliseconds = nowTimestamp - taskTimestamp;
                if (sincePingMilliseconds < AGENT_REACHABLE_RENEW_MILLISECONDS) {
                    continue;
                }
            }

            final PingAgentTask pingTask = new PingAgentTask();
            pingTask.setConsumerId(agentId);
            if (agentState != null && agentState.isMachineReachableLifecycle()) {
                pingTask.setExpectedNumberOfAgentRestartsInAgentState(agentState.getNumberOfAgentStarts());
                pingTask.setExpectedNumberOfMachineRestartsInAgentState(agentState.getNumberOfMachineStarts());
            }
            addNewTaskIfNotExists(newTasks, pingTask);
        }
    }

    private void orchestrateAgent(List<Task> newTasks, long nowTimestamp, URI agentId) {

        final AgentState agentState = getAgentState(agentId);
        final LifecycleState desiredLifecycle =
                state.getDeploymentPlan().getAgentPlan(agentId).get().getLifecycleState();

        if (isUnreachable(nowTimestamp, agentId, agentState)) {
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

    private boolean isUnreachable(long nowTimestamp, URI agentId, AgentState agentState) {
        Preconditions.checkNotNull(agentState);
        final AgentPingHealth pingHealth = getAgentPingHealth(agentId, nowTimestamp);

        return agentState.isMachineReachableLifecycle() &&
               pingHealth == AgentPingHealth.AGENT_UNREACHABLE;
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

    private AgentPingHealth getAgentPingHealth(URI agentId, long nowTimestamp) {

        AgentPingHealth health = AgentPingHealth.UNDETERMINED;

        // look for ping that should have been consumed by now --> AGENT_NOT_RESPONDING
        AgentState agentState = getAgentState(agentId);

        // look for ping that was consumed just recently --> AGENT_REACHABLE
        if (agentState != null) {
            final long taskTimestamp = agentState.getLastPingSourceTimestamp();
            final long sincePingMilliseconds = nowTimestamp - taskTimestamp;
            if (sincePingMilliseconds <= AGENT_UNREACHABLE_MILLISECONDS) {
                // ping was consumed just recently
                health = AgentPingHealth.AGENT_REACHABLE;
            }
        }

        if (health == AgentPingHealth.UNDETERMINED) {

            Iterable<Task> pendingTasks = taskReader.getPendingTasks(agentId);
            for (final Task task : pendingTasks) {
                Preconditions.checkState(
                        task.getProducerId().equals(orchestratorId),
                        "All agent tasks are assumed to be from this orchestrator");
                if (task instanceof PingAgentTask) {
                    PingAgentTask pingAgentTask = (PingAgentTask) task;
                    Integer expectedNumberOfAgentRestartsInAgentState =
                            pingAgentTask.getExpectedNumberOfAgentRestartsInAgentState();
                    Integer expectedNumberOfMachineRestartsInAgentState =
                            pingAgentTask.getExpectedNumberOfMachineRestartsInAgentState();
                    if (expectedNumberOfAgentRestartsInAgentState == null && agentState != null) {
                        Preconditions.checkState(expectedNumberOfMachineRestartsInAgentState == null);
                        if (agentState.isMachineReachableLifecycle()) {
                            // agent started after ping sent. Wait for next ping
                        } else {
                            // agent not reachable because it was not started yet
                            health = AgentPingHealth.AGENT_UNREACHABLE;
                        }
                    } else if (expectedNumberOfMachineRestartsInAgentState != null &&
                               agentState != null &&
                               expectedNumberOfMachineRestartsInAgentState != agentState.getNumberOfMachineStarts()) {
                        Preconditions.checkState(
                                expectedNumberOfMachineRestartsInAgentState < agentState.getNumberOfMachineStarts(),
                                "Could not have sent ping to a machine that was not restarted yet");
                        // machine restarted after ping sent. Wait for next ping
                    } else if (expectedNumberOfAgentRestartsInAgentState != null &&
                               agentState != null &&
                               expectedNumberOfAgentRestartsInAgentState != agentState.getNumberOfAgentStarts()) {
                        Preconditions.checkState(
                                expectedNumberOfAgentRestartsInAgentState < agentState.getNumberOfAgentStarts(),
                                "Could not have sent ping to an agent that was not restarted yet");
                        // agent restarted after ping sent. Wait for next ping
                    } else {
                        final long taskTimestamp = task.getProducerTimestamp();
                        final long notRespondingMilliseconds = nowTimestamp - taskTimestamp;
                        if (notRespondingMilliseconds > AGENT_UNREACHABLE_MILLISECONDS) {
                            // ping should have been consumed by now
                            health = AgentPingHealth.AGENT_UNREACHABLE;
                        }
                    }
                }
            }
        }

        return health;
    }

    private AgentState getAgentState(URI agentId) {
        return ServiceUtils.getAgentState(stateReader, agentId);
    }

    /**
     * A three state enum that determines if the agent can process tasks.
     */
    public enum AgentPingHealth {
        UNDETERMINED, AGENT_UNREACHABLE, AGENT_REACHABLE
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
