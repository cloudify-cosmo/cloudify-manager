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
import org.cloudifysource.cosmo.mock.MockPlannerManagement;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
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
import static org.cloudifysource.cosmo.AssertServiceState.getReachableAgentIds;
import static org.cloudifysource.cosmo.AssertServiceState.getReachableInstanceIds;

/**
 * Unit tests that check integration of {@link org.cloudifysource.cosmo.service.ServiceGridOrchestrator},
 * {@link org.cloudifysource.cosmo.service.ServiceGridDeploymentPlanner},
 * {@link org.cloudifysource.cosmo.service.ServiceGridCapacityPlanner}.
 *
 * @author itaif
 * @since 0.1
 */
public class ServiceGridIntegrationTest extends AbstractServiceGridTest<MockPlannerManagement> {

    @Override
    protected MockPlannerManagement createMockManagement() {
        return new MockPlannerManagement();
    }

    /**
     * Tests deployment of 1 instance.
     */
    @Test
    public void installSingleInstanceServiceTest() {
        Assert.assertTrue(Iterables.isEmpty(getReachableAgentIds(getManagement(), "web")));
        installService("web", "tomcat", 1);
        execute();
        assertOneTomcatInstance("web", getManagement());
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests deployment of 2 instances.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void installMultipleInstanceServiceTest() {
        installService("web", "tomcat", 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }


    /**
     * Tests machine failover, and restart by the orchestrator.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void machineFailoverTest() {
        installService("web", "tomcat", 1);
        execute();
        killOnlyMachine("web");
        execute();
        final int numberOfAgentStarts = 1;
        final int numberOfMachineStarts = 2;
        assertSingleServiceInstance(
                getManagement(), "web", new LifecycleName("tomcat"),
                numberOfAgentStarts, numberOfMachineStarts);
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Test agent process failed, and restarted automatically by
     * reliable watchdog running on the same machine.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void agentRestartTest() {
        installService("web", "tomcat", 1);
        execute();
        restartOnlyAgent("web");
        execute();
        final int numberOfAgentStarts = 2;
        final int numberOfMachineStarts = 1;
        assertSingleServiceInstance(
                getManagement(), "web", new LifecycleName("tomcat"),
                numberOfAgentStarts, numberOfMachineStarts);
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests change in plan from 1 instance to 2 instances.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void scaleOutServiceTest() {
        installService("web", "tomcat", 1);
        execute();
        scaleService("web", "tomcat", 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Tests change in plan from 1 instance to 2 instances.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void scaleInServiceTest() {
        installService("web", "tomcat", 2);
        execute();
        scaleService("web", "tomcat", 1);
        execute();
        assertTomcatScaledInFrom2To1(getManagement());
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Tests uninstalling tomcat service when machine hosting service instance failed.
     */
    @Test//(dependsOnMethods = {"machineFailoverTest" })
    public void machineFailoverUninstallServiceTest() {
        installService("web", "tomcat", 1);
        execute();
        killOnlyMachine("web");
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledUnreachable(getManagement(), 1);
    }

    /**
     * Tests management state recovery from crash.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void managementRestartTest() {
        installService("web", "tomcat", 1);
        execute();
        getManagement().restart();
        execute();
        assertOneTomcatInstance("web", getManagement());
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests management state recovery from crash when one of the agents also failed.
     * This test is similar to scaleOut test. Since there is one agent, and the plan is two agents.
     */
    @Test(dependsOnMethods = {"managementRestartTest", "agentRestartTest" })
    public void managementRestartAndOneAgentRestartTest() {
        installService("web", "tomcat", 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        restartAgent(getManagement().getAgentId("web/2"));
        getManagement().restart();
        execute();
        assertTwoTomcatInstances(getManagement(),
                expectedAgentZeroNotRestartedAgentOneRestarted(getManagement()),
                expectedBothMachinesNotRestarted(getManagement()));
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Install two services, each with one instance.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void installTwoSingleInstanceServicesTest() {
        installService("web", "tomcat", 1);
        installService("db", "cassandra", 1);
        execute();
        assertServiceInstalledWithOneInstance(getManagement(), "web", new LifecycleName("tomcat"));
        assertServiceInstalledWithOneInstance(getManagement(), "db",
                new LifecycleName("cassandra"));
        Assert.assertEquals(
                Iterables.size(
                        getReachableInstanceIds(getManagement(), "web",
                                new LifecycleName("tomcat"))),
                1);
        Assert.assertEquals(
                Iterables.size(
                        getReachableInstanceIds(getManagement(), "db",
                                new LifecycleName("cassandra"))),
                1);
        uninstallService("web", "tomcat");
        uninstallService("db", "cassandra");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    @Test(dependsOnMethods = {"scaleOutServiceTest", "scaleInServiceTest", "setInstancePropertyTest" })
    public void scalingRulesTest() {

        installService("web", "tomcat", 1);
        final ServiceScalingRule rule = new ServiceScalingRule();
        rule.setPropertyName("request-throughput");
        rule.setLowThreshold(1);
        rule.setHighThreshold(10);
        scalingrule("web", "tomcat", rule);
        execute();

        assertOneTomcatInstance("web", getManagement());
        final URI instanceId1 =
                getManagement().getServiceInstanceId("web/1", new LifecycleName("tomcat"));
        setServiceInstanceProperty(instanceId1, "request-throughput", 100);
        execute();
        assertTwoTomcatInstances(getManagement());
        final URI instanceId2 =
                getManagement().getServiceInstanceId("web/2", new LifecycleName("tomcat"));
        setServiceInstanceProperty(instanceId1, "request-throughput", 0);
        setServiceInstanceProperty(instanceId2, "request-throughput", 0);
        execute();
        assertTomcatScaledInFrom2To1(getManagement());
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void setInstancePropertyTest() {

        final String propertyName = "hello";
        final String propertyValue = "world";

        installService("web", "tomcat", 1);
        execute();
        assertOneTomcatInstance("web", getManagement());
        URI instanceId =
                getManagement().getServiceInstanceId("web" + "/1", new LifecycleName("tomcat"));
        setServiceInstanceProperty(instanceId, propertyName, propertyValue);
        execute();
        Assert.assertEquals(getServiceInstanceProperty(propertyName, instanceId), propertyValue);
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
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

    private void scalingrule(String aliasGroup, String serviceName, ServiceScalingRule rule) {
        rule.setServiceId(getManagement().getServiceId(aliasGroup, new LifecycleName(serviceName)));
        ScalingRulesTask task = new ScalingRulesTask();
        task.setScalingRule(rule);
        getManagement().submitTask(getManagement().getCapacityPlannerId(), task);
    }

    private URI getOnlyReachableAgentId(String aliasGroup) {
        return Iterables.getOnlyElement(getReachableAgentIds(getManagement(), aliasGroup));
    }

    private void installService(String aliasGroup, String serviceName, int numberOfInstances) {
        final int minNumberOfInstances = 1;
        final int maxNumberOfInstances = 2;
        ServiceConfig serviceConfig = new ServiceConfig();
        serviceConfig.setDisplayName(serviceName);
        serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
        serviceConfig.setMaxNumberOfInstances(maxNumberOfInstances);
        serviceConfig.setMinNumberOfInstances(minNumberOfInstances);
        serviceConfig.setServiceId(getManagement().getServiceId(aliasGroup, new LifecycleName(serviceName)));
        serviceConfig.setAliasGroup(aliasGroup);
        final InstallServiceTask installServiceTask = new InstallServiceTask();
        installServiceTask.setServiceConfig(serviceConfig);
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), installServiceTask);
    }

    private void uninstallService(String aliasGroup, String serviceName) {
        URI serviceId = getManagement().getServiceId(aliasGroup, new LifecycleName(serviceName));
        final UninstallServiceTask uninstallServiceTask = new UninstallServiceTask();
        uninstallServiceTask.setServiceId(serviceId);
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), uninstallServiceTask);
    }

    private void scaleService(String aliasGroup, String serviceName, int plannedNumberOfInstances) {
        final ScaleServiceTask scaleServiceTask = new ScaleServiceTask();
        URI serviceId = getManagement().getServiceId(aliasGroup, new LifecycleName(serviceName));
        scaleServiceTask.setServiceId(serviceId);
        scaleServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
        scaleServiceTask.setProducerTimestamp(currentTimeMillis());
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), scaleServiceTask);
    }

    private void execute() {
        execute(getManagement().getCapacityPlannerId(),
                getManagement().getDeploymentPlannerId(),
                getManagement().getOrchestratorId(),
                getManagement().getAgentProbeId());
    }

    private void killOnlyMachine(String aliasGroup) {
        killMachine(getOnlyReachableAgentId(aliasGroup));
    }

    private void restartOnlyAgent(String aliasGroup) {
        restartAgent(getOnlyReachableAgentId(aliasGroup));
    }
}
