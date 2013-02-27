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
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.testng.Assert;

import java.net.URI;
import java.util.Map;

/**
 * Unit test utility class for management assertions.
 * @author itaif
 * @since 0.1
 */
public class AssertServiceState {

    private AssertServiceState() { }

    public static void assertServiceInstalledWithOneInstance(MockManagement management, String serviceName) {
        final int machineStarts = 1;
        final int agentStarts = 1;
        assertServiceInstalledWithOneInstance(management, serviceName, agentStarts, machineStarts);
    }

    public static void assertSingleServiceInstance(MockManagement management, String serviceName) {
        final int machineStarts = 1;
        final int agentStarts = 1;
        assertSingleServiceInstance(management, serviceName, agentStarts, machineStarts);
    }

    public static void assertSingleServiceInstance(
            MockManagement management, String serviceName,
            int numberOfAgentStarts, int numberOfMachineStarts) {

        Assert.assertEquals(management.getDeploymentPlan().getServices().size(), 1);
        Assert.assertEquals(
                Iterables.size(getAgentIds(management)), 1, "Expected 1 agent id, " +
                "instead found: " + getAgentIds(management));
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(management, serviceName)), 1);
        assertServiceInstalledWithOneInstance(
                management, serviceName,
                numberOfAgentStarts, numberOfMachineStarts);
    }

    private static void assertServiceInstalledWithOneInstance(
            MockManagement management, String serviceName,
            int numberOfAgentStarts, int numberOfMachineStarts) {

        final URI serviceId = management.getServiceId(serviceName);
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        final URI instanceId = Iterables.getOnlyElement(serviceState.getInstanceIds());
        final ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
        TaskConsumerHistory instanceTasksHistory = getTasksHistory(management, instanceId);
        Assert.assertEquals(
                Iterables.size(Iterables.filter(instanceTasksHistory.getTasksHistory(), new Predicate<Task>() {

                    @Override
                    public boolean apply(Task task) {
                        if (task instanceof ServiceInstanceTask) {
                            return ((ServiceInstanceTask) task).getLifecycle().equals("service_started");
                        }
                        return false;
                    }
                }))
                , numberOfMachineStarts,
                "History: " + Iterables.toString(
                        Iterables.transform(instanceTasksHistory.getTasksHistory(), new Function<Task, String>() {
                            final ObjectMapper mapper = StreamUtils.newObjectMapper();

                            @Override
                            public String apply(Task task) {
                                return StreamUtils.toJson(mapper, task);
                            }
                        })));

        final URI agentId = instanceState.getAgentId();
        Assert.assertEquals(instanceState.getServiceId(), serviceId);
        Assert.assertTrue(instanceState.isLifecycle("service_started"));

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
        final ServiceConfig serviceConfig = deploymentPlan.getServiceById(serviceId).getServiceConfig();
        Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
    }

    private static int countMachineLifecycleTasks(TaskConsumerHistory instanceTasksHistory, final String lifecycle) {
        return Iterables.size(Iterables.filter(instanceTasksHistory.getTasksHistory(), new Predicate<Task>() {

            @Override
            public boolean apply(Task task) {
                if (task instanceof MachineLifecycleTask) {
                    return ((MachineLifecycleTask) task).getLifecycle().equals(lifecycle);
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

    public static Iterable<URI> getServiceInstanceIds(MockManagement management, String serviceName) {
        return getStateIdsStartingWith(management, StreamUtils.newURI(management.getStateServerUri() +
                "services/" + serviceName + "/instances/"));
    }

    private static Iterable<URI> getStateIdsStartingWith(MockManagement management, final URI uri) {
        return Iterables.filter(
                management.getStateReader().getElementIdsStartingWith(uri),
                new Predicate<URI>() {

                    @Override
                    public boolean apply(URI stateId) {
                        return stateId.toString().endsWith("/");
                    }
                });
    }


    public static Iterable<URI> getAgentIds(MockManagement management) {
        final URI agentsPrefix = StreamUtils.newURI(management.getStateServerUri() + "agents/");
        return getStateIdsStartingWith(management, agentsPrefix);
    }

    public static void assertTwoTomcatInstances(
            MockManagement management,
            Map<URI, Integer> numberOfAgentStartsPerAgent,
            Map<URI, Integer> numberOfMachineStartsPerAgent) {
        final URI serviceId = management.getServiceId("tomcat");
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()), 2);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        Iterable<URI> instanceIds = getStateIdsStartingWith(management, StreamUtils.newURI(management
                .getStateServerUri() +
                "services/tomcat/instances/"));
        Assert.assertEquals(Iterables.size(instanceIds), 2);

        final ServiceGridDeploymentPlan deploymentPlan = management.getDeploymentPlan();
        Assert.assertEquals(
                Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
        Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);

        Iterable<URI> agentIds = getAgentIds(management);
        int numberOfAgents = Iterables.size(agentIds);
        Assert.assertEquals(numberOfAgents, 2);
        for (int i = 0; i < numberOfAgents; i++) {

            URI agentId = Iterables.get(agentIds, i);
            AgentState agentState = management.getAgentState(agentId);
            Assert.assertTrue(agentState.isLifecycle(agentState.getMachineReachableLifecycle()));
            Assert.assertEquals(agentState.getNumberOfAgentStarts(), (int) numberOfAgentStartsPerAgent.get(agentId));
            Assert.assertEquals(
                    agentState.getNumberOfMachineStarts(),
                    (int) numberOfMachineStartsPerAgent.get(agentId));
            URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
            Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
            ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
            Assert.assertEquals(instanceState.getServiceId(), serviceId);
            Assert.assertEquals(instanceState.getAgentId(), agentId);
            Assert.assertTrue(instanceState.isLifecycle("service_started"));
            Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        }
    }

    public static void assertTwoTomcatInstances(MockManagement management) {
        assertTwoTomcatInstances(management, expectedBothAgentsNotRestarted(management),
                expectedBothMachinesNotRestarted(management));
    }

    public static ImmutableMap<URI, Integer> expectedBothAgentsNotRestarted(MockManagement management) {
        return ImmutableMap.<URI, Integer>builder()
                .put(management.getAgentId(0), 1)
                .put(management.getAgentId(1), 1)
                .build();
    }

    public static ImmutableMap<URI, Integer> expectedBothMachinesNotRestarted(MockManagement management) {
        return ImmutableMap.<URI, Integer>builder()
                .put(management.getAgentId(0), 1)
                .put(management.getAgentId(1), 1)
                .build();
    }

    public static ImmutableMap<URI, Integer> expectedAgentZeroNotRestartedAgentOneRestarted(
            MockManagement management) {
        return ImmutableMap.<URI, Integer>builder()
                .put(management.getAgentId(0), 1)
                .put(management.getAgentId(1), 2)
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
        final URI serviceId = management.getServiceId("tomcat");
        Assert.assertFalse(management.getDeploymentPlan().isServiceExists(serviceId));
        final ServiceState serviceState = management.getServiceState(serviceId);
        Assert.assertEquals(serviceState.getInstanceIds().size(), 0);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_UNINSTALLED));

        for (URI instanceId: getServiceInstanceIds(management, "tomcat")) {
            ServiceInstanceState instanceState = management.getServiceInstanceState(instanceId);
            if (instanceUnreachable) {
                Assert.assertTrue(instanceState.isLifecycle("machine_unreachable"));
            } else {
                Assert.assertEquals(instanceState.getLifecycle(), "service_cleaned");
            }
            URI agentId = instanceState.getAgentId();
            AgentState agentState = management.getAgentState(agentId);
            Assert.assertTrue(agentState.isMachineTerminatedLifecycle());
        }
    }

    public static void assertOneTomcatInstance(MockManagement management) {
        assertSingleServiceInstance(management, "tomcat");
    }

    public static void assertTomcatScaledInFrom2To1(MockManagement management) {
        assertServiceInstalledWithOneInstance(management, "tomcat");
        final AgentState agentState0 = management.getAgentState(management.getAgentId(0));
        Assert.assertTrue(agentState0.isLifecycle(agentState0.getMachineReachableLifecycle()));
        final AgentState agentState1 = management.getAgentState(management.getAgentId(1));
        Assert.assertTrue(agentState1.isLifecycle(agentState1.getMachineTerminatedLifecycle()));
        Assert.assertTrue(management.getServiceInstanceState(management.getServiceInstanceId("tomcat", 0))
                .isLifecycle("service_started"));
        Assert.assertTrue(management.getServiceInstanceState(management.getServiceInstanceId("tomcat", 1))
                .isLifecycle("service_cleaned"));
    }
}
