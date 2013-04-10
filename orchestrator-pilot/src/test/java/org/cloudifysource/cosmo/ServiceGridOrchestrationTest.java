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
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.service.id.AliasGroupId;
import org.cloudifysource.cosmo.service.id.AliasId;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
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
import static org.cloudifysource.cosmo.AssertServiceState.getReachableInstanceIds;

/**
 * Unit Tests for {@link org.cloudifysource.cosmo.service.ServiceGridOrchestrator}.
 * @author itaif
 * @since 0.1
 */
public class ServiceGridOrchestrationTest extends AbstractServiceGridTest<MockManagement> {

    @Override
    protected MockManagement createMockManagement() {
        return new MockManagement();
    }

    /**
     * Tests deployment of 1 instance.
     */
    @Test
    public void installSingleInstanceServiceTest() {
        Assert.assertTrue(Iterables.isEmpty(getAgentIds(getManagement(), web)));
        installService(web, tomcat, 1);
        execute();
        assertOneTomcatInstance(web, getManagement());
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests deployment of 2 instances.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void installMultipleInstanceServiceTest() {
        installService(web, tomcat, 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        uninstallService(web, tomcat, 2);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Tests machine failover, and restart by the orchestrator.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void machineFailoverTest() {
        installService(web, tomcat, 1);
        execute();
        killOnlyMachine(web);
        execute();
        final int numberOfAgentStarts = 1;
        final int numberOfMachineStarts = 2;
        assertSingleServiceInstance(
                getManagement(), web, tomcat,
                numberOfAgentStarts, numberOfMachineStarts);
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Test agent process failed, and restarted automatically by
     * reliable watchdog running on the same machine.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void agentRestartTest() {
        installService(web, tomcat, 1);
        execute();
        restartOnlyAgent(web);
        execute();
        final int numberOfAgentStarts = 2;
        final int numberOfMachineStarts = 1;
        assertSingleServiceInstance(
                getManagement(), web, tomcat,
                numberOfAgentStarts, numberOfMachineStarts);
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests change in plan from 1 instance to 2 instances.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void scaleOutServiceTest() {
        installService(web, tomcat, 1);
        execute();
        scaleService(web, tomcat, 1, 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        uninstallService(web, tomcat, 2);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Tests change in plan from 1 instance to 2 instances.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void scaleInServiceTest() {
        installService(web, tomcat, 2);
        execute();
        scaleService(web, tomcat, 2, 1);
        execute();
        assertTomcatScaledInFrom2To1(getManagement());
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Tests uninstalling tomcat service when machine hosting service instance failed.
     */
    @Test(dependsOnMethods = {"machineFailoverTest" })
    public void machineFailoverUninstallServiceTest() {
        installService(web, tomcat, 1);
        execute();
        killOnlyMachine(web);
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledUnreachable(getManagement(), 1);
    }

    /**
     * Tests management state recovery from crash.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void managementRestartTest() {
        installService(web, tomcat, 1);
        execute();

        getManagement().restart();
        //simulates recovery of planner
        installService(web, tomcat, 1);

        execute();
        assertOneTomcatInstance(web, getManagement());
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests management state recovery from crash when one of the agents also failed.
     * This test is similar to scaleOut test. Since there is one agent, and the plan is two agents.
     */
    @Test(dependsOnMethods = {"managementRestartTest", "agentRestartTest" })
    public void managementRestartAndOneAgentRestartTest() {
        final LifecycleName lifecycleName = tomcat;
        final AliasGroupId aliasGroup = new AliasGroupId("web");
        installService(aliasGroup, lifecycleName, 2);
        execute();
        assertTwoTomcatInstances(getManagement());
        restartAgent(getManagement().getAgentId(aliasGroup.newAliasId(2)));
        getManagement().restart();
        //simulates recovery of planner
        installService(aliasGroup, lifecycleName, 2);

        execute();
        assertTwoTomcatInstances(
                getManagement(),
                expectedAgentZeroNotRestartedAgentOneRestarted(getManagement()),
                expectedBothMachinesNotRestarted(getManagement()));
        uninstallService(aliasGroup, lifecycleName, 2);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 2);
    }

    /**
     * Install two services, each with one instance.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void installTwoSingleInstanceServicesTest() {
        final AliasGroupId web = new AliasGroupId("web");
        installService(web, tomcat, 1);
        installService(db, cassandra, 1);
        execute();
        assertServiceInstalledWithOneInstance(getManagement(), web, tomcat);
        assertServiceInstalledWithOneInstance(getManagement(), db, cassandra);
        Assert.assertEquals(
                Iterables.size(
                        getReachableInstanceIds(getManagement(), web, tomcat)),
                1);
        Assert.assertEquals(
                Iterables.size(
                        getReachableInstanceIds(getManagement(), db, cassandra)),
                1);
        uninstallService(web, tomcat, 1);
        uninstallService(db, cassandra, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" })
    public void setInstancePropertyTest() {

        final String propertyName = "hello";
        final String propertyValue = "world";

        installService(web, tomcat, 1);
        execute();
        assertOneTomcatInstance(web, getManagement());
        URI instanceId = getManagement().getServiceInstanceId(web.newAliasId(1), tomcat);
        setServiceInstanceProperty(instanceId, propertyName, propertyValue);
        execute();
        Assert.assertEquals(getServiceInstanceProperty(propertyName, instanceId), propertyValue);
        uninstallService(web, tomcat, 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    /**
     * Tests zombie agent CLOUDIFY-1593
     * Enable when implementation is complete.
     */
    @Test(dependsOnMethods = {"installSingleInstanceServiceTest" }, enabled = true)
    public void detectZombieAgentTest() {
        Assert.assertTrue(Iterables.isEmpty(getAgentIds(getManagement(), web)));
        startZombieAgentAndThenHealthyAgent();
        installService(web, tomcat, 1);
        execute();
        final int numberOfAgentStarts = 1;
        final int numberOfMachineStarts = 2;
        final int numberOfInstanceStarts = 1;
        assertSingleServiceInstance(
                getManagement(), web, tomcat,
                numberOfAgentStarts, numberOfMachineStarts, numberOfInstanceStarts);

        uninstallService(web, tomcat, 1);
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

    private URI getOnlyAgentId(AliasGroupId aliasGroup) {
        return Iterables.getOnlyElement(getAgentIds(getManagement(), aliasGroup));
    }

    private void installService(AliasGroupId aliasGroup, LifecycleName lifecycleName, int numberOfInstances) {
        cos(aliasGroup, "plan_set", lifecycleName.getName(),
                "--instances", String.valueOf(numberOfInstances),
                "--min_instances", "1",
                "--max_instances", "2");

        for (int i = 1; i <= numberOfInstances; i++) {
            final AliasId alias = aliasGroup.newAliasId(i);
            startServiceInstance(alias, lifecycleName);
        }
    }

    private void uninstallService(AliasGroupId aliasGroup, LifecycleName lifecycleName, int numberOfInstances) {
        cos(aliasGroup, "plan_unset", lifecycleName.getName());

        for (int i = 1; i <= numberOfInstances; i++) {
            final AliasId alias = aliasGroup.newAliasId(i);
            cleanServiceInstance(alias, lifecycleName);
        }
    }

    private void startServiceInstance(AliasId alias, LifecycleName lifecycleName) {

        final String prefix = lifecycleName.getName() + "_";
        cos(alias, "lifecycle_set", lifecycleName.getName(),
                prefix + "cleaned<-->" + prefix + "installed<-->" + prefix + "configured->" + prefix + "started" +
                        "," + prefix + "started->" + prefix + "stopped->" + prefix + "cleaned",
                "--begin", prefix + "cleaned",
                "--end", prefix + "started");

        cos(alias, prefix + "started");
        cos(alias, "cloudmachine_reachable");
    }


    private void cleanServiceInstance(AliasId alias, LifecycleName lifecycleName) {
        final String prefix = lifecycleName.getName() + "_";

        cos(alias, prefix + "cleaned");
        cos(alias, "cloudmachine_terminated");
    }

    private void scaleService(
            AliasGroupId aliasGroup,
            LifecycleName lifecycleName,
            int oldNumberOfInstances,
            int newNumberOfInstances) {

        for (int i = oldNumberOfInstances + 1; i <= newNumberOfInstances; i++) {

            final AliasId alias = aliasGroup.newAliasId(i);
            startServiceInstance(alias, lifecycleName);
        }

        for (int i = oldNumberOfInstances; i > newNumberOfInstances; i--) {

            final AliasId alias = aliasGroup.newAliasId(i);
            cleanServiceInstance(alias, lifecycleName);
        }
    }

    private void execute() {
        execute(getManagement().getOrchestratorId(), getManagement().getAgentProbeId());
    }

    private void killOnlyMachine(AliasGroupId aliasGroup) {
        killMachine(getOnlyAgentId(aliasGroup));
    }

    private void restartOnlyAgent(AliasGroupId aliasGroup) {
        restartAgent(getOnlyAgentId(aliasGroup));
    }
}
