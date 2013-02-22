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

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.StartAgentTask;
import org.cloudifysource.cosmo.agent.tasks.StartMachineTask;
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridOrchestratorState;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
import org.cloudifysource.cosmo.service.tasks.UpdateDeploymentPlanTask;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.testng.Assert;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Map;

public class ServiceGridOrchestrationTest extends AbstractServiceGridTest<MockManagement> {

    @Override
    protected MockManagement createMockManagement() {
        return new MockManagement();
    }

    /**
     * Tests deployment of 1 instance
     */
    @Test
    public void installSingleInstanceServiceTest() {
        Assert.assertTrue(Iterables.isEmpty(getAgentIds()));
        installService("tomcat", 1);
        execute();
        assertOneTomcatInstance();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests deployment of 2 instances
     */
    @Test
    public void installMultipleInstanceServiceTest() {
        installService("tomcat", 2);
        execute();
        assertTwoTomcatInstances();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }


    /**
     * Tests machine failover, and restart by the orchestrator
     */
    @Test
    public void machineFailoverTest() {
        installService("tomcat", 1);
        execute();
        killOnlyMachine();
        execute();
        final int numberOfAgentRestarts = 0;
        final int numberOfMachineRestarts = 1;
        assertSingleServiceInstance("tomcat", numberOfAgentRestarts, numberOfMachineRestarts);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Test agent process failed, and restarted automatically by
     * reliable watchdog running on the same machine
     */
    @Test
    public void agentRestartTest() {
        installService("tomcat", 1);
        execute();
        restartOnlyAgent();
        execute();
        final int numberOfAgentRestarts = 1;
        final int numberOfMachineRestarts = 0;
        assertSingleServiceInstance("tomcat", numberOfAgentRestarts, numberOfMachineRestarts);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests change in plan from 1 instance to 2 instances
     */
    @Test
    public void scaleOutServiceTest() {
        installService("tomcat", 1);
        execute();
        scaleService("tomcat",2);
        execute();
        assertTwoTomcatInstances();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests change in plan from 1 instance to 2 instances
     */
    @Test
    public void scaleInServiceTest() {
        installService("tomcat", 2);
        execute();
        scaleService("tomcat", 1);
        execute();
        assertTomcatScaledInFrom2To1();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests uninstalling tomcat service when machine hosting service instance failed.
     */
    @Test
    public void killMachineUninstallServiceTest() {
        installService("tomcat",1);
        execute();
        killOnlyMachine();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledUnreachable();
    }

    /**
     * Tests management state recovery from crash
     */
    @Test
    public void managementRestartTest() {
        installService("tomcat", 1);
        execute();

        getManagement().restart();
        //simulates recovery of planner
        installService("tomcat", 1);

        execute();
        assertOneTomcatInstance();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests management state recovery from crash when one of the agents also failed.
     * This test is similar to scaleOut test. Since there is one agent, and the plan is two agents.
     */
    @Test
    public void managementRestartAndOneAgentRestartTest() {
        installService("tomcat", 2);
        execute();
        assertTwoTomcatInstances();
        restartAgent(getManagement().getAgentId(1));
        getManagement().restart();
        //simulates recovery of planner
        installService("tomcat", 2);

        execute();
        assertTwoTomcatInstances(expectedAgentZeroNotRestartedAgentOneRestarted(), expectedBothMachinesNotRestarted());
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Install two services, each with one instance
     */
    @Test
    public void installTwoSingleInstanceServicesTest(){
        installServices("tomcat", 1, "cassandra", 1);
        execute();
        assertServiceInstalledWithOneInstance("tomcat");
        assertServiceInstalledWithOneInstance("cassandra");
        Assert.assertEquals(Iterables.size(getServiceInstanceIds("tomcat")), 1);
        Assert.assertEquals(Iterables.size(getServiceInstanceIds("cassandra")), 1);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    @Test
    public void setInstancePropertyTest() {

        final String propertyName = "hellow";
        final String propertyValue = "world";

        installService("tomcat", 1);
        execute();
        assertOneTomcatInstance();
        URI instanceId = getManagement().getServiceInstanceId("tomcat", 0);
        setServiceInstanceProperty(instanceId, propertyName, propertyValue);
        execute();
        Assert.assertEquals(getServiceInstanceProperty(propertyName, instanceId), propertyValue);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully();
    }

    private Object getServiceInstanceProperty(final String propertyName, URI instanceId) {
        return getManagement().getServiceInstanceState(instanceId).getProperty(propertyName);
    }

    private void setServiceInstanceProperty(
            URI instanceId,
            String propertyName,
            Object propertyValue) {

        SetInstancePropertyTask task = new SetInstancePropertyTask();
        task.setStateId(instanceId);
        task.setPropertyName(propertyName);
        task.setPropertyValue(propertyValue);

        final URI agentId = getManagement().getServiceInstanceState(instanceId).getAgentId();
        getManagement().submitTask(agentId, task);
    }

    private void assertOneTomcatInstance() {
        assertSingleServiceInstance("tomcat");
    }

    private void assertTomcatScaledInFrom2To1() {
        assertServiceInstalledWithOneInstance("tomcat");
        Assert.assertTrue(getManagement().getAgentState(getManagement().getAgentId(0))
                .isProgress(AgentState.Progress.AGENT_STARTED));
        Assert.assertTrue(getManagement().getAgentState(getManagement().getAgentId(1))
                .isProgress(AgentState.Progress.MACHINE_TERMINATED));
        Assert.assertTrue(getManagement().getServiceInstanceState(getManagement().getServiceInstanceId("tomcat", 0))
                .isProgress("service_started"));
        Assert.assertTrue(getManagement().getServiceInstanceState(getManagement().getServiceInstanceId("tomcat", 1))
                .isProgress("service_uninstalled"));
    }

    private void assertTomcatUninstalledGracefully() {
        boolean instanceUnreachable = false;
        assertTomcatUninstalled(instanceUnreachable);
    }

    private void assertTomcatUninstalledUnreachable() {
        boolean instanceUnreachable = true;
        assertTomcatUninstalled(instanceUnreachable);
    }

    private void assertTomcatUninstalled(boolean instanceUnreachable) {
        final URI serviceId = getManagement().getServiceId("tomcat");
        Assert.assertFalse(getDeploymentPlan().isServiceExists(serviceId));
        final ServiceState serviceState = getManagement().getServiceState(serviceId);
        Assert.assertEquals(serviceState.getInstanceIds().size(), 0);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_UNINSTALLED));

        for (URI instanceId: getServiceInstanceIds("tomcat")) {
            ServiceInstanceState instanceState = getManagement().getServiceInstanceState(instanceId);
            if (instanceUnreachable) {
                Assert.assertTrue(instanceState.isUnreachable());
            }
            else {
                Assert.assertTrue(instanceState.isProgress("service_uninstalled"));
            }
            URI agentId = instanceState.getAgentId();
            AgentState agentState = getManagement().getAgentState(agentId);
            Assert.assertTrue(agentState.isProgress(AgentState.Progress.MACHINE_TERMINATED));
        }
    }

    private void assertServiceInstalledWithOneInstance(String serviceName) {
        int zeroMachineRestarts = 0;
        int zeroAgentRestarts = 0;
        assertServiceInstalledWithOneInstance(serviceName, zeroAgentRestarts, zeroMachineRestarts);
    }

    private void assertSingleServiceInstance(String serviceName) {
        final int zeroAgentRestarts = 0;
        final int zeroMachineRestarts = 0;
        assertSingleServiceInstance(serviceName, zeroAgentRestarts, zeroMachineRestarts);
    }

    private void assertSingleServiceInstance(String serviceName, int numberOfAgentRestarts, int numberOfMachineRestarts) {
        Assert.assertEquals(getDeploymentPlan().getServices().size(), 1);
        Assert.assertEquals(Iterables.size(getAgentIds()), 1, "Expected 1 agent id, instead found: "+ getAgentIds());
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(serviceName)),1);
        assertServiceInstalledWithOneInstance(serviceName, numberOfAgentRestarts, numberOfMachineRestarts);
    }

    private void assertServiceInstalledWithOneInstance(
            String serviceName, int numberOfAgentRestarts, int numberOfMachineRestarts) {
        final URI serviceId = getManagement().getServiceId(serviceName);
        final ServiceState serviceState = getManagement().getServiceState(serviceId);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        final URI instanceId = Iterables.getOnlyElement(serviceState.getInstanceIds());
        final ServiceInstanceState instanceState = getManagement().getServiceInstanceState(instanceId);
        TaskConsumerHistory instanceTasksHistory = getTasksHistory(instanceId);
        Assert.assertEquals(Iterables.size(Iterables.filter(instanceTasksHistory.getTasksHistory(), new Predicate<Task>() {

            @Override
            public boolean apply(Task task) {
                if (task instanceof ServiceInstanceTask) {
                    return ((ServiceInstanceTask)task).getLifecycle().equals("service_started");
                }
                return false;
            }
        }))
        ,1+numberOfMachineRestarts);

        final URI agentId = instanceState.getAgentId();
        Assert.assertEquals(instanceState.getServiceId(), serviceId);
        Assert.assertTrue(instanceState.isProgress("service_started"));

        final AgentState agentState = getManagement().getAgentState(agentId);
        Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()),instanceId);
        Assert.assertTrue(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
        Assert.assertEquals(agentState.getNumberOfAgentRestarts(), numberOfAgentRestarts);
        Assert.assertEquals(agentState.getNumberOfMachineRestarts(), numberOfMachineRestarts);

        TaskConsumerHistory agentTasksHistory = getTasksHistory(agentId);
        Assert.assertEquals(Iterables.size(Iterables.filter(agentTasksHistory.getTasksHistory(),StartMachineTask.class)),1+numberOfMachineRestarts);
        Assert.assertEquals(Iterables.size(Iterables.filter(agentTasksHistory.getTasksHistory(),StartAgentTask.class)),1+numberOfMachineRestarts);

        final ServiceGridDeploymentPlan deploymentPlan = getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId(serviceId)), instanceId);
        final ServiceConfig serviceConfig = deploymentPlan.getServiceById(serviceId).getServiceConfig();
        Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
    }

    private TaskConsumerHistory getTasksHistory(final URI stateId) {
        final URI tasksHistoryId = ServiceUtils.toTasksHistoryId(stateId);
        EtagState<TaskConsumerHistory> etagState = getManagement().getStateReader()
                .get(tasksHistoryId, TaskConsumerHistory.class);
        Preconditions.checkNotNull(etagState);
        return etagState.getState();
    }

    private ServiceGridDeploymentPlan getDeploymentPlan() {
        return getManagement().getStateReader()
               .get(getManagement().getOrchestratorId(), ServiceGridOrchestratorState.class)
               .getState()
               .getDeploymentPlan();
    }

    private URI getOnlyAgentId() {
        return Iterables.getOnlyElement(getAgentIds());
    }

    private void assertTwoTomcatInstances() {

        assertTwoTomcatInstances(expectedBothAgentsNotRestarted(), expectedBothMachinesNotRestarted());
    }

    private void assertTwoTomcatInstances(Map<URI,Integer> numberOfAgentRestartsPerAgent, Map<URI,Integer> numberOfMachineRestartsPerAgent) {
        final URI serviceId = getManagement().getServiceId("tomcat");
        final ServiceState serviceState = getManagement().getServiceState(serviceId);
        Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()), 2);
        Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
        Iterable<URI> instanceIds = getStateIdsStartingWith(StreamUtils.newURI(getManagement().getStateServerUri()
                + "services/tomcat/instances/"));
        Assert.assertEquals(Iterables.size(instanceIds),2);

        final ServiceGridDeploymentPlan deploymentPlan = getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
        Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);

        Iterable<URI> agentIds = getAgentIds();
        int numberOfAgents = Iterables.size(agentIds);
        Assert.assertEquals(numberOfAgents, 2);
        for (int i = 0 ; i < numberOfAgents; i++) {

            URI agentId = Iterables.get(agentIds, i);
            AgentState agentState = getManagement().getAgentState(agentId);
            Assert.assertTrue(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
            Assert.assertEquals(agentState.getNumberOfAgentRestarts(), (int) numberOfAgentRestartsPerAgent.get(agentId));
            Assert.assertEquals(agentState.getNumberOfMachineRestarts(), (int) numberOfMachineRestartsPerAgent.get(agentId));
            URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
            Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
            ServiceInstanceState instanceState = getManagement().getServiceInstanceState(instanceId);
            Assert.assertEquals(instanceState.getServiceId(), serviceId);
            Assert.assertEquals(instanceState.getAgentId(), agentId);
            Assert.assertTrue(instanceState.isProgress("service_started"));
            Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        }
    }

    private void installService(String name, int numberOfInstances) {
        final UpdateDeploymentPlanTask task = new UpdateDeploymentPlanTask();
        task.setDeploymentPlan(newServiceGridDeploymentPlan(name, numberOfInstances));
        getManagement().submitTask(getManagement().getOrchestratorId(), task);
    }

    private void installServices(String name1, int numberOfInstances1, String name2, int numberOfInstances2) {
        final UpdateDeploymentPlanTask task = new UpdateDeploymentPlanTask();
        ServiceDeploymentPlan serviceDeploymentPlan1 =
                newServiceDeploymentPlan(name1, numberOfInstances1, /*offset=*/0);
        ServiceDeploymentPlan serviceDeploymentPlan2 =
                newServiceDeploymentPlan(name2, numberOfInstances2, /*offset=*/ numberOfInstances1);
        ServiceGridDeploymentPlan servicesDeploymentPlan = new ServiceGridDeploymentPlan();
        servicesDeploymentPlan.setServices(Lists.newArrayList(serviceDeploymentPlan1, serviceDeploymentPlan2));
        task.setDeploymentPlan(servicesDeploymentPlan);
        getManagement().submitTask(getManagement().getOrchestratorId(), task);
    }

    private void scaleService(String name, int numberOfInstances) {
        installService(name, numberOfInstances);
    }

    private ServiceGridDeploymentPlan newServiceGridDeploymentPlan(String name, int numberOfInstances) {
        ServiceDeploymentPlan serviceDeploymentPlan = newServiceDeploymentPlan(name, numberOfInstances, 0);
        ServiceGridDeploymentPlan servicesDeploymentPlan = new ServiceGridDeploymentPlan();
        servicesDeploymentPlan.setServices(Lists.newArrayList(serviceDeploymentPlan));
        return servicesDeploymentPlan;
    }

    private ServiceDeploymentPlan newServiceDeploymentPlan(String name, int numberOfInstances, int offset) {
        final int minNumberOfInstances = 1;
        final int maxNumberOfInstances = 2;
        ServiceConfig serviceConfig = new ServiceConfig();
        serviceConfig.setDisplayName(name);
        serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
        serviceConfig.setMaxNumberOfInstances(maxNumberOfInstances);
        serviceConfig.setMinNumberOfInstances(minNumberOfInstances);
        final URI serviceId = getManagement().getServiceId(name);
        serviceConfig.setServiceId(serviceId);
        ServiceDeploymentPlan serviceDeploymentPlan = new ServiceDeploymentPlan();
        serviceDeploymentPlan.setServiceConfig(serviceConfig);
        for (int i = 0 ; i < numberOfInstances ; i++) {
            final URI agentId = getManagement().getAgentId(i + offset);
            final URI instanceId = getManagement().getServiceInstanceId(name, i + offset);
            serviceDeploymentPlan.addInstance(instanceId, agentId);
        }
        return serviceDeploymentPlan;
    }

    private void uninstallAllServices() {
        final UpdateDeploymentPlanTask task = new UpdateDeploymentPlanTask();
        task.setDeploymentPlan(new ServiceGridDeploymentPlan());
        getManagement().submitTask(getManagement().getOrchestratorId(), task);
    }

    private void execute() {
        execute(getManagement().getOrchestratorId());
    }

    private Iterable<URI> getServiceInstanceIds(String serviceName) {
        return getStateIdsStartingWith(StreamUtils.newURI(getManagement().getStateServerUri()
                + "services/" + serviceName + "/instances/"));
    }

    private Iterable<URI> getStateIdsStartingWith(final URI uri) {
        return Iterables.filter(
                getManagement().getStateReader().getElementIdsStartingWith(uri),
                new Predicate<URI>(){

                    @Override
                    public boolean apply(URI stateId) {
                        return stateId.toString().endsWith("/");
                    }});
    }


    private Iterable<URI> getAgentIds() {
        return getStateIdsStartingWith(StreamUtils.newURI(getManagement().getStateServerUri() + "agents/"));
    }

    private void killOnlyMachine() {
        killMachine(getOnlyAgentId());
    }

    private void restartOnlyAgent() {
        restartAgent(getOnlyAgentId());
    }

    private ImmutableMap<URI, Integer> expectedBothAgentsNotRestarted() {
        return ImmutableMap.<URI,Integer>builder()
                 .put(getManagement().getAgentId(0), 0)
                 .put(getManagement().getAgentId(1), 0)
                 .build();
    }

    private ImmutableMap<URI, Integer> expectedBothMachinesNotRestarted() {
        return ImmutableMap.<URI,Integer>builder()
                 .put(getManagement().getAgentId(0), 0)
                 .put(getManagement().getAgentId(1), 0)
                 .build();
    }

    private ImmutableMap<URI, Integer> expectedAgentZeroNotRestartedAgentOneRestarted() {
        return ImmutableMap.<URI,Integer>builder()
         .put(getManagement().getAgentId(0), 0)
         .put(getManagement().getAgentId(1), 1)
         .build();
    }


}
