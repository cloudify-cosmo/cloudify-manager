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

import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceInstanceDeploymentPlan;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
import org.cloudifysource.cosmo.service.tasks.UpdateDeploymentPlanTask;
import org.testng.Assert;
import org.testng.annotations.Test;

import java.net.URI;

import static org.cloudifysource.cosmo.AssertServiceState.assertOneTomcatInstance;
import static org.cloudifysource.cosmo.AssertServiceState.assertServiceInstalledWithOneInstance;
import static org.cloudifysource.cosmo.AssertServiceState.assertSingleServiceInstance;
import static org.cloudifysource.cosmo.AssertServiceState.assertTomcatScaledInFrom2To1;
import static org.cloudifysource.cosmo.AssertServiceState.assertTomcatUninstalledGracefully;
import static org.cloudifysource.cosmo.AssertServiceState.assertTomcatUninstalledUnreachable;
import static org.cloudifysource.cosmo.AssertServiceState.assertTwoTomcatInstances;
import static org.cloudifysource.cosmo.AssertServiceState.expectedAgentZeroNotRestartedAgentOneRestarted;
import static org.cloudifysource.cosmo.AssertServiceState.expectedBothMachinesNotRestarted;
import static org.cloudifysource.cosmo.AssertServiceState.getAgentIds;
import static org.cloudifysource.cosmo.AssertServiceState.getServiceInstanceIds;

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
        Assert.assertTrue(Iterables.isEmpty(getAgentIds(getManagement())));
        installService("tomcat", 1);
        execute();
        assertOneTomcatInstance(getManagement());
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Tests deployment of 2 instances
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void installMultipleInstanceServiceTest() {
        installService("tomcat", 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Tests machine failover, and restart by the orchestrator
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void machineFailoverTest() {
        installService("tomcat", 1);
        execute();
        killOnlyMachine();
        execute();
        final int numberOfAgentStarts = 1;
        final int numberOfMachineStarts = 2;
        assertSingleServiceInstance(
                getManagement(), "tomcat",
                numberOfAgentStarts, numberOfMachineStarts);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Test agent process failed, and restarted automatically by
     * reliable watchdog running on the same machine
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void agentRestartTest() {
        installService("tomcat", 1);
        execute();
        restartOnlyAgent();
        execute();
        final int numberOfAgentStarts = 2;
        final int numberOfMachineStarts = 1;
        assertSingleServiceInstance(
                getManagement(), "tomcat",
                numberOfAgentStarts, numberOfMachineStarts);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Tests change in plan from 1 instance to 2 instances
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void scaleOutServiceTest() {
        installService("tomcat", 1);
        execute();
        scaleService("tomcat", 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Tests change in plan from 1 instance to 2 instances
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void scaleInServiceTest() {
        installService("tomcat", 2);
        execute();
        scaleService("tomcat", 1);
        execute();
        assertTomcatScaledInFrom2To1(getManagement());
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Tests uninstalling tomcat service when machine hosting service instance failed.
     */
    @Test(dependsOnMethods = {"machineFailoverTest"})
    public void machineFailoverUninstallServiceTest() {
        installService("tomcat", 1);
        execute();
        killOnlyMachine();
        uninstallAllServices();
        execute();
        assertTomcatUninstalledUnreachable(getManagement());
    }

    /**
     * Tests management state recovery from crash
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void managementRestartTest() {
        installService("tomcat", 1);
        execute();

        getManagement().restart();
        //simulates recovery of planner
        installService("tomcat", 1);

        execute();
        assertOneTomcatInstance(getManagement());
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Tests management state recovery from crash when one of the agents also failed.
     * This test is similar to scaleOut test. Since there is one agent, and the plan is two agents.
     */
    @Test(dependsOnMethods = {"managementRestartTest","agentRestartTest"})
    public void managementRestartAndOneAgentRestartTest() {
        installService("tomcat", 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        restartAgent(getManagement().getAgentId(1));
        getManagement().restart();
        //simulates recovery of planner
        installService("tomcat", 2);

        execute();
        assertTwoTomcatInstances(
                getManagement(),
                expectedAgentZeroNotRestartedAgentOneRestarted(getManagement()),
                expectedBothMachinesNotRestarted(getManagement()));
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Install two services, each with one instance
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void installTwoSingleInstanceServicesTest(){
        installServices("tomcat", 1, "cassandra", 1);
        execute();
        assertServiceInstalledWithOneInstance(getManagement(), "tomcat");
        assertServiceInstalledWithOneInstance(getManagement(), "cassandra");
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(getManagement(),"tomcat")), 1);
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(getManagement(),"cassandra")), 1);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void setInstancePropertyTest() {

        final String propertyName = "hellow";
        final String propertyValue = "world";

        installService("tomcat", 1);
        execute();
        assertOneTomcatInstance(getManagement());
        URI instanceId = getManagement().getServiceInstanceId("tomcat", 0);
        setServiceInstanceProperty(instanceId, propertyName, propertyValue);
        execute();
        Assert.assertEquals(getServiceInstanceProperty(propertyName, instanceId), propertyValue);
        uninstallAllServices();
        execute();
        assertTomcatUninstalledGracefully(getManagement());
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

    private URI getOnlyAgentId() {
        return Iterables.getOnlyElement(getAgentIds(getManagement()));
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
        serviceConfig.setServiceId(getManagement().getServiceId(name));
        serviceConfig.setInstanceLifecycleStateMachine(new LifecycleStateMachine(Lists.newArrayList(
                "service_cleaned",
                "service_stopped",
                "service_started"
        )));

        ServiceDeploymentPlan serviceDeploymentPlan = new ServiceDeploymentPlan();
        serviceDeploymentPlan.setServiceConfig(serviceConfig);
        for (int i = 0 ; i < numberOfInstances ; i++) {
            final ServiceInstanceDeploymentPlan instancePlan = new ServiceInstanceDeploymentPlan();
            instancePlan.setAgentId(getManagement().getAgentId(i + offset));
            instancePlan.setInstanceId(getManagement().getServiceInstanceId(name, i + offset));
            instancePlan.setDesiredLifecycle("service_started");
            serviceDeploymentPlan.addInstance(instancePlan);
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

    private void killOnlyMachine() {
        killMachine(getOnlyAgentId());
    }

    private void restartOnlyAgent() {
        restartAgent(getOnlyAgentId());
    }
}
