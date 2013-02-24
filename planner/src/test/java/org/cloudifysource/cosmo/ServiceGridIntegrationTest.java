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
import org.cloudifysource.cosmo.mock.MockPlannerManagement;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceScalingRule;
import org.cloudifysource.cosmo.service.tasks.InstallServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScaleServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScalingRulesTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
import org.cloudifysource.cosmo.service.tasks.UninstallServiceTask;
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

public class ServiceGridIntegrationTest extends AbstractServiceGridTest<MockPlannerManagement> {

    @Override
    protected MockPlannerManagement createMockManagement() {
        return new MockPlannerManagement();
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
        uninstallService("tomcat");
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
        uninstallService("tomcat");
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
        final int numberOfAgentRestarts = 0;
        final int numberOfMachineRestarts = 1;
        assertSingleServiceInstance(getManagement(), "tomcat", numberOfAgentRestarts, numberOfMachineRestarts);
        uninstallService("tomcat");
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
        final int numberOfAgentRestarts = 1;
        final int numberOfMachineRestarts = 0;
        assertSingleServiceInstance(getManagement(), "tomcat", numberOfAgentRestarts, numberOfMachineRestarts);
        uninstallService("tomcat");
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
        uninstallService("tomcat");
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
        uninstallService("tomcat");
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
        uninstallService("tomcat");
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
        execute();
        assertOneTomcatInstance(getManagement());
        uninstallService("tomcat");
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
        execute();
        assertTwoTomcatInstances(getManagement(),
                expectedAgentZeroNotRestartedAgentOneRestarted(getManagement()),
                expectedBothMachinesNotRestarted(getManagement()));
        uninstallService("tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    /**
     * Install two services, each with one instance
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void installTwoSingleInstanceServicesTest(){
        installService("tomcat", 1);
        installService("cassandra", 1);
        execute();
        assertServiceInstalledWithOneInstance(getManagement(), "tomcat");
        assertServiceInstalledWithOneInstance(getManagement(), "cassandra");
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(getManagement(), "tomcat")), 1);
        Assert.assertEquals(Iterables.size(getServiceInstanceIds(getManagement(), "cassandra")), 1);
        uninstallService("tomcat");
        uninstallService("cassandra");
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    @Test(dependsOnMethods = {"scaleOutServiceTest","scaleInServiceTest","setInstancePropertyTest"})
    public void scalingRulesTest() {

        installService("tomcat", 1);
        final ServiceScalingRule rule = new ServiceScalingRule();
        rule.setPropertyName("request-throughput");
        rule.setLowThreshold(1);
        rule.setHighThreshold(10);
        scalingrule("tomcat", rule);
        execute();

        assertOneTomcatInstance(getManagement());
        final URI instanceId0 = getManagement().getServiceInstanceId("tomcat", 0);
        setServiceInstanceProperty(instanceId0, "request-throughput", 100);
        execute();
        assertTwoTomcatInstances(getManagement());
        final URI instanceId1 = getManagement().getServiceInstanceId("tomcat", 1);
        setServiceInstanceProperty(instanceId0, "request-throughput", 0);
        setServiceInstanceProperty(instanceId1, "request-throughput", 0);
        execute();
        assertTomcatScaledInFrom2To1(getManagement());
        uninstallService("tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement());
    }

    @Test(dependsOnMethods = {"installSingleInstanceServiceTest"})
    public void setInstancePropertyTest() {

        final String propertyName = "hello";
        final String propertyValue = "world";

        installService("tomcat", 1);
        execute();
        assertOneTomcatInstance(getManagement());
        URI instanceId = getManagement().getServiceInstanceId("tomcat", 0);
        setServiceInstanceProperty(instanceId, propertyName, propertyValue);
        execute();
        Assert.assertEquals(getServiceInstanceProperty(propertyName, instanceId), propertyValue);
        uninstallService("tomcat");
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

    private void scalingrule(String serviceName, ServiceScalingRule rule) {
        rule.setServiceId(getManagement().getServiceId(serviceName));
        ScalingRulesTask task = new ScalingRulesTask();
        task.setScalingRule(rule);
        getManagement().submitTask(getManagement().getCapacityPlannerId(), task);
    }

    private URI getOnlyAgentId() {
        return Iterables.getOnlyElement(getAgentIds(getManagement()));
    }

    private void installService(String name, int numberOfInstances) {
        final int minNumberOfInstances = 1;
        final int maxNumberOfInstances = 2;
        ServiceConfig serviceConfig = new ServiceConfig();
        serviceConfig.setDisplayName(name);
        serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
        serviceConfig.setMaxNumberOfInstances(maxNumberOfInstances);
        serviceConfig.setMinNumberOfInstances(minNumberOfInstances);
        serviceConfig.setServiceId(getManagement().getServiceId(name));
        serviceConfig.setInstanceLifecycleStateMachine(Lists.newArrayList(
                "service_cleaned",
                "service_stopped",
                "service_started"
        ));
        final InstallServiceTask installServiceTask = new InstallServiceTask();
        installServiceTask.setServiceConfig(serviceConfig);
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), installServiceTask);
    }

    private void uninstallService(String name) {
        URI serviceId = getManagement().getServiceId(name);
        final UninstallServiceTask uninstallServiceTask = new UninstallServiceTask();
        uninstallServiceTask.setServiceId(serviceId);
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), uninstallServiceTask);
    }

    private void scaleService(String serviceName, int plannedNumberOfInstances) {
        final ScaleServiceTask scaleServiceTask = new ScaleServiceTask();
        URI serviceId = getManagement().getServiceId(serviceName);
        scaleServiceTask.setServiceId(serviceId);
        scaleServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
        scaleServiceTask.setProducerTimestamp(currentTimeMillis());
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), scaleServiceTask);
    }

    private void execute() {
        execute(getManagement().getCapacityPlannerId(),
                getManagement().getDeploymentPlannerId(),
                getManagement().getOrchestratorId());
    }

    private void killOnlyMachine() {
        killMachine(getOnlyAgentId());
    }

    private void restartOnlyAgent() {
        restartAgent(getOnlyAgentId());
    }
}
