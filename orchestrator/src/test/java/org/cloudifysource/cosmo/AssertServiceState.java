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
package org.cloudifysource.cosmo;

import com.beust.jcommander.internal.Lists;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.MachineLifecycleTask;
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.testng.Assert;

import java.net.URI;
import java.util.List;
import java.util.Map;

/**
 * Unit test utility class for management assertions.
 * @author itaif
 * @since 0.1
 */
public class AssertServiceState {

    private AssertServiceState() { }

    public static void assertServiceInstalledWithOneInstance(
            MockManagement management,
            String aliasGroup,
            LifecycleName lifecycleName) {
        final int machineStarts = 1;
        final int agentStarts = 1;
        assertServiceInstalledWithOneInstance(management, aliasGroup, lifecycleName, agentStarts, machineStarts);
    }

    public static void assertSingleServiceInstance(MockManagement management,
                                                   String aliasGroup, LifecycleName lifecycleName) {
        final int machineStarts = 1;
        final int agentStarts = 1;
        assertSingleServiceInstance(management, aliasGroup, lifecycleName, agentStarts, machineStarts);
    }

    public static void assertSingleServiceInstance(
            MockManagement management, String aliasGroup, LifecycleName lifecycleName,
            int numberOfAgentStarts, int numberOfMachineStarts) {

        Assert.assertEquals(management.getDeploymentPlan().getServices().size(), 1);
        Assert.assertEquals(
                Iterables.size(getAgentIds(management, aliasGroup)), 1, "Expected 1 agent id, " +
                "instead found: " + getAgentIds(management, aliasGroup));
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(management, aliasGroup, lifecycleName)), 1);
        assertServiceInstalledWithOneInstance(
                management, aliasGroup, lifecycleName,
                numberOfAgentStarts, numberOfMachineStarts);
    }

    private static void assertServiceInstalledWithOneInstance(
            MockManagement management, String aliasGroup, final LifecycleName lifecycleName,
            int numberOfAgentStarts, int numberOfMachineStarts) {

        final URI serviceId = management.getServiceId(aliasGroup, lifecycleName);
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(serviceState.getProgress(), ServiceState.Progress.SERVICE_INSTALLED);
        final URI instanceId = Iterables.getOnlyElement(serviceState.getInstanceIds());
        final ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
        TaskConsumerHistory instanceTasksHistory = getTasksHistory(management, instanceId);
        final LifecycleState startedState = new LifecycleState(lifecycleName.getName() + "_started");
        Assert.assertEquals(
                countServiceInstanceLifecycleTasks(
                        instanceTasksHistory,
                        startedState),
                numberOfMachineStarts,
                taskHistoryToString(instanceTasksHistory));

        final URI agentId = instanceState.getAgentId();
        Assert.assertEquals(instanceState.getServiceId(), serviceId);
        Assert.assertTrue(instanceState.getStateMachine().isLifecycleState(startedState));
        Assert.assertTrue(instanceState.isReachable());

        final AgentState agentState = management.getAgentState(agentId);
        Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()), instanceId);
        Assert.assertTrue(agentState.isMachineReachableLifecycle());
        Assert.assertEquals(agentState.getNumberOfAgentStarts(), numberOfAgentStarts);
        Assert.assertEquals(agentState.getNumberOfMachineStarts(), numberOfMachineStarts);

        TaskConsumerHistory agentTasksHistory = getTasksHistory(management, agentId);
        Assert.assertEquals(
                countMachineLifecycleTasks(agentTasksHistory, agentState.getMachineStartedLifecycle()),
                numberOfMachineStarts);
        Assert.assertEquals(
                countMachineLifecycleTasks(agentTasksHistory, agentState.getMachineReachableLifecycle()),
                numberOfMachineStarts);

        final ServiceGridDeploymentPlan deploymentPlan = management.getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId(serviceId)), instanceId);
        final ServiceConfig serviceConfig = deploymentPlan.getServicePlan(serviceId).get().getServiceConfig();
        Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
    }

    private static String taskHistoryToString(TaskConsumerHistory instanceTasksHistory) {
        return "History: " + Iterables.toString(
                Iterables.transform(instanceTasksHistory.getTasksHistory(), new Function<Task, String>() {
                    final ObjectMapper mapper = StreamUtils.newObjectMapper();

                    @Override
                    public String apply(Task task) {
                        return StreamUtils.toJson(mapper, task);
                    }
                }));
    }

    private static int countServiceInstanceLifecycleTasks(TaskConsumerHistory instanceTasksHistory,
                                                          LifecycleState expectedLifecycleState) {
        final Predicate<Task> predicate = findServiceInstanceLifecycleTaskPredicate(expectedLifecycleState);
        return Iterables.size(Iterables.filter(instanceTasksHistory.getTasksHistory(), predicate));
    }

    private static Predicate<Task> findServiceInstanceLifecycleTaskPredicate(
            final LifecycleState expectedLifecycleState) {
        return new Predicate<Task>() {

                @Override
                public boolean apply(Task task) {
                    if (task instanceof ServiceInstanceTask) {
                        return ((ServiceInstanceTask) task).getLifecycleState().equals(expectedLifecycleState);
                    }
                    return false;
                }
            };
    }

    private static int countMachineLifecycleTasks(
            final TaskConsumerHistory instanceTasksHistory,
            final LifecycleState lifecycleState) {
        return Iterables.size(Iterables.filter(instanceTasksHistory.getTasksHistory(), new Predicate<Task>() {

            @Override
            public boolean apply(Task task) {
                if (task instanceof MachineLifecycleTask) {
                    return ((MachineLifecycleTask) task).getLifecycleState().equals(lifecycleState);
                }
                return false;
            }
        }));
    }

    private static TaskConsumerHistory getTasksHistory(MockManagement management, final URI stateId) {
        final URI tasksHistoryId = ServiceUtils.toTasksHistoryId(stateId);
        EtagState<TaskConsumerHistory> etagState = management.getStateReader()
                .get(tasksHistoryId, TaskConsumerHistory.class);
        Preconditions.checkNotNull(etagState);
        return etagState.getState();
    }

    public static Iterable<URI> getAgentIds(MockManagement management, String aliasGroup) {
        List<URI> uris = Lists.newArrayList();
        for (int i = 1; true; i++) {
            final String alias = aliasGroup + "/" + i + "/";
            final URI agentId = management.getAgentId(alias);
            if (management.getAgentState(agentId) != null) {
                uris.add(agentId);
            } else {
                break;
            }
        }
        return uris;
    }

    public static Iterable<URI> getServiceInstanceIds(MockManagement management, String aliasGroup,
                                                      LifecycleName lifecycleName) {
        List<URI> uris = Lists.newArrayList();
        for (int i = 1; true; i++) {
            final String alias = aliasGroup + "/" + i + "/";
            final URI instanceId = management.getServiceInstanceId(alias, lifecycleName);
            if (management.getServiceInstanceState(instanceId) != null) {
                uris.add(instanceId);
            } else {
                break;
            }
        }
        return uris;
    }

    public static void assertTwoTomcatInstances(
            MockManagement management,
            Map<URI, Integer> numberOfAgentStartsPerAgent,
            Map<URI, Integer> numberOfMachineStartsPerAgent) {
        final LifecycleName lifecycleName = new LifecycleName("tomcat");
        final String aliasGroup = "web";
        final URI serviceId = management.getServiceId(aliasGroup, lifecycleName);
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()), 2);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        Iterable<URI> instanceIds = getServiceInstanceIds(management, aliasGroup, lifecycleName);
        Assert.assertEquals(Iterables.size(instanceIds), 2);

        final ServiceGridDeploymentPlan deploymentPlan = management.getDeploymentPlan();
        Assert.assertEquals(
                Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
        Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);

        Iterable<URI> agentIds = getAgentIds(management, aliasGroup);
        int numberOfAgents = Iterables.size(agentIds);
        Assert.assertEquals(numberOfAgents, 2);
        for (int i = 0; i < numberOfAgents; i++) {

            URI agentId = Iterables.get(agentIds, i);
            AgentState agentState = management.getAgentState(agentId);
            Assert.assertTrue(agentState.getStateMachine().isLifecycleState(agentState.getMachineReachableLifecycle()));
            Assert.assertEquals(agentState.getNumberOfAgentStarts(), (int) numberOfAgentStartsPerAgent.get(agentId),
                    "Unexpected number of agent restarts in " + agentId);
            final int numberOfMachineStarts = (int) numberOfMachineStartsPerAgent.get(agentId);
            Assert.assertEquals(
                    agentState.getNumberOfMachineStarts(),
                    numberOfMachineStarts,
                    "Unexpected number of machine restarts in " + agentId);
            URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
            Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
            ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
            Assert.assertEquals(instanceState.getServiceId(), serviceId);
            Assert.assertEquals(instanceState.getAgentId(), agentId);
            Assert.assertTrue(instanceState.getStateMachine()
                    .isLifecycleState(new LifecycleState(lifecycleName.getName() + "_started")));
            Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        }
    }

    public static void assertTwoTomcatInstances(MockManagement management) {
        assertTwoTomcatInstances(management, expectedBothAgentsNotRestarted(management),
                expectedBothMachinesNotRestarted(management));
    }

    public static ImmutableMap<URI, Integer> expectedBothAgentsNotRestarted(MockManagement management) {
        return ImmutableMap.<URI, Integer>builder()
                .put(management.getAgentId("web/1"), 1)
                .put(management.getAgentId("web/2"), 1)
                .build();
    }

    public static ImmutableMap<URI, Integer> expectedBothMachinesNotRestarted(MockManagement management) {
        return ImmutableMap.<URI, Integer>builder()
                .put(management.getAgentId("web/1"), 1)
                .put(management.getAgentId("web/2"), 1)
                .build();
    }

    public static ImmutableMap<URI, Integer> expectedAgentZeroNotRestartedAgentOneRestarted(
            MockManagement management) {
        return ImmutableMap.<URI, Integer>builder()
                .put(management.getAgentId("web/1"), 1)
                .put(management.getAgentId("web/2"), 2)
                .build();
    }


    public static void assertTomcatUninstalledGracefully(MockManagement management) {
        boolean instanceUnreachable = false;
        assertTomcatUninstalled(management, instanceUnreachable);
    }

    public static void assertTomcatUninstalledUnreachable(MockManagement management) {
        boolean instanceUnreachable = true;
        assertTomcatUninstalled(management, instanceUnreachable);
    }

    private static void assertTomcatUninstalled(MockManagement management, boolean instanceUnreachable) {
        final URI serviceId = management.getServiceId("web", new LifecycleName("tomcat"));
        Assert.assertFalse(management.getDeploymentPlan().isServiceExists(serviceId));
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(serviceState.getInstanceIds().size(), 0);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_UNINSTALLED));

        for (URI instanceId: getServiceInstanceIds(management, "web", new LifecycleName("tomcat"))) {
            ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
            Assert.assertFalse(instanceState.isReachable());
            if (instanceUnreachable) {
                Assert.assertEquals(
                        instanceState.getStateMachine().getCurrentState(),
                        new LifecycleState("tomcat_started"));
            } else {
                Assert.assertEquals(
                        instanceState.getStateMachine().getCurrentState(),
                        new LifecycleState("tomcat_cleaned"));
            }
            URI agentId = instanceState.getAgentId();
            AgentState agentState = management.getAgentState(agentId);
            Assert.assertEquals(
                agentState.getStateMachine().getCurrentState(),
                agentState.getMachineTerminatedLifecycle());
        }
    }

    public static void assertOneTomcatInstance(MockManagement management) {
        assertSingleServiceInstance(management, "web", new LifecycleName("tomcat"));
    }

    public static void assertTomcatScaledInFrom2To1(MockManagement management) {
        assertServiceInstalledWithOneInstance(management, "web", new LifecycleName("tomcat"));
        final AgentState agentState0 = management.getAgentState(management.getAgentId("web/1"));
        Assert.assertTrue(agentState0.getStateMachine().isLifecycleState(agentState0.getMachineReachableLifecycle()));
        final AgentState agentState1 = management.getAgentState(management.getAgentId("web/2"));
        Assert.assertTrue(agentState1.getStateMachine().isLifecycleState(agentState1.getMachineTerminatedLifecycle()));
        final URI tomcat1Id = management.getServiceInstanceId("web/1", new LifecycleName("tomcat"));
        Assert.assertTrue(management.getServiceInstanceState(tomcat1Id)
                          .getStateMachine().isLifecycleState(new LifecycleState("tomcat_started")));
        final URI tomcat2Id = management.getServiceInstanceId("web/2", new LifecycleName("tomcat"));
        Assert.assertTrue(management.getServiceInstanceState(tomcat2Id)
                          .getStateMachine().isLifecycleState(new LifecycleState("tomcat_cleaned")));
    }
}
