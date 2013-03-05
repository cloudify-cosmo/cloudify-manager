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

import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.mock.MockPlannerManagement;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlannerState;
import org.cloudifysource.cosmo.service.tasks.InstallServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScaleServiceTask;
import org.cloudifysource.cosmo.service.tasks.UninstallServiceTask;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.testng.Assert;
import org.testng.annotations.Test;

import java.net.URI;

/**
 * Unit tests for {@link org.cloudifysource.cosmo.service.ServiceGridDeploymentPlanner}.
 * @since 0.1
 * @author itaif
 */
public class ServiceGridDeploymentPlannerTest extends AbstractServiceGridTest<MockPlannerManagement> {

    @Override
    protected MockPlannerManagement createMockManagement() {
        return new MockPlannerManagement();
    }

    /**
     * Tests deployment of 1 instance.
     */
    @Test
    public void installSingleInstanceServiceTest() {
        Assert.assertTrue(Iterables.isEmpty(getAgentIds()));
        installService("web", "tomcat", 1);
        execute();
        assertOneTomcatInstance();
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests deployment of 2 instances.
     */
    @Test(dependsOnMethods =  {"installSingleInstanceServiceTest" })
    public void installMultipleInstanceServiceTest() {
        installService("web", "tomcat", 2);
        execute();
        assertTwoTomcatInstances();
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests change in plan from 1 instance to 2 instances.
     */
    @Test(dependsOnMethods =  {"installSingleInstanceServiceTest" })
    public void scaleOutServiceTest() {
        installService("web", "tomcat", 1);
        execute();
        scaleService("web", "tomcat", 2);
        execute();
        assertTwoTomcatInstances();
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests change in plan from 1 instance to 2 instances.
     */
    @Test(dependsOnMethods =  {"installSingleInstanceServiceTest" })
    public void scaleInServiceTest() {
        installService("web", "tomcat", 2);
        execute();
        scaleService("web", "tomcat", 1);
        execute();
        assertTomcatScaledInFrom2To1();
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests management state recovery from crash.
     */
    @Test(dependsOnMethods =  {"installSingleInstanceServiceTest" })
    public void managementRestartTest() {
        installService("web", "tomcat", 1);
        execute();
        getManagement().restart();
        execute();
        assertOneTomcatInstance();
        uninstallService("web", "tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Install two services, each with one instance.
     */
    @Test(dependsOnMethods =  {"installSingleInstanceServiceTest" })
    public void installTwoSingleInstanceServicesTest() {
        installService("web", "tomcat", 1);
        installService("db", "cassandra", 1);
        execute();
        assertServiceInstalledWithOneInstance("web", "tomcat");
        assertServiceInstalledWithOneInstance("db", "cassandra");
        uninstallService("web", "tomcat");
        uninstallService("db", "cassandra");
        execute();
        assertTomcatUninstalledGracefully();
    }

    private void assertOneTomcatInstance() {
        assertSingleServiceInstance("tomcat");
    }

    private void assertTomcatScaledInFrom2To1() {
        assertServiceInstalledWithOneInstance("web", "tomcat");
    }

    private void assertTomcatUninstalledGracefully() {
        final URI serviceId = getServiceId("web", "tomcat");
        Assert.assertFalse(getManagement().getDeploymentPlan().isServiceExists(serviceId));
    }

    private URI getServiceId(String aliasGroup, String serviceName) {
        return getManagement().getServiceId(aliasGroup, new LifecycleName(serviceName));
    }

    private void assertSingleServiceInstance(String serviceName) {

        Assert.assertNotNull(getDeploymentPlannerState());
        final ServiceConfig serviceConfig = Iterables.getOnlyElement(
                getDeploymentPlannerState().getCapacityPlan().getServices());
        Assert.assertEquals(serviceConfig.getDisplayName(), serviceName);

        Assert.assertEquals(getManagement().getDeploymentPlan().getServices().size(), 1);
    }

    private void assertServiceInstalledWithOneInstance(
            String aliasGroup, String serviceName) {
        if (!aliasGroup.endsWith("/")) {
            aliasGroup += "/";
        }
        final String alias = aliasGroup + 1;
        final URI instanceId = getManagement().getServiceInstanceId(alias, new LifecycleName(serviceName));
        final URI serviceId = getServiceId(aliasGroup, serviceName);
        final URI agentId = getManagement().getAgentId(alias);

        Assert.assertEquals(
                getDeploymentPlannerState().getCapacityPlan().getServiceById(serviceId).getPlannedNumberOfInstances(),
                1);

        final ServiceGridDeploymentPlan deploymentPlan = getManagement().getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId(serviceId)), instanceId);
        final ServiceConfig serviceConfig = deploymentPlan.getServicePlan(serviceId).get().getServiceConfig();
        Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
    }

    private String getAliasGroup(String serviceName) {
        return serviceName + "/";
    }

    private ServiceGridDeploymentPlannerState getDeploymentPlannerState() {
        return getManagement().getStateReader()
                .get(getManagement().getDeploymentPlannerId(), ServiceGridDeploymentPlannerState.class).getState();
    }

    private void assertTwoTomcatInstances() {
        final URI serviceId = getServiceId("web", "tomcat");

        Assert.assertEquals(
                getDeploymentPlannerState().getCapacityPlan().getServiceById(serviceId).getPlannedNumberOfInstances(),
                2);
        final ServiceGridDeploymentPlan deploymentPlan = getManagement().getDeploymentPlan();
        Assert.assertEquals(
                Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
        Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);
    }

    private void installService(String aliasGroup, String serviceName, int numberOfInstances) {
        final int minNumberOfInstances = 1;
        final int maxNumberOfInstances = 2;
        ServiceConfig serviceConfig = new ServiceConfig();
        serviceConfig.setDisplayName(serviceName);
        serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
        serviceConfig.setMaxNumberOfInstances(maxNumberOfInstances);
        serviceConfig.setMinNumberOfInstances(minNumberOfInstances);
        serviceConfig.setServiceId(getServiceId(aliasGroup, serviceName));
        serviceConfig.setAliasGroup(aliasGroup);
        final InstallServiceTask installServiceTask = new InstallServiceTask();
        installServiceTask.setServiceConfig(serviceConfig);
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), installServiceTask);
    }

    private void uninstallService(String aliasGroup, String serviceName) {
        URI serviceId = getServiceId(aliasGroup, serviceName);
        final UninstallServiceTask uninstallServiceTask = new UninstallServiceTask();
        uninstallServiceTask.setServiceId(serviceId);
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), uninstallServiceTask);
    }

    private void scaleService(String aliasGroup, String serviceName, int plannedNumberOfInstances) {
        final ScaleServiceTask scaleServiceTask = new ScaleServiceTask();
        URI serviceId = getServiceId(aliasGroup, serviceName);
        scaleServiceTask.setServiceId(serviceId);
        scaleServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
        scaleServiceTask.setProducerTimestamp(currentTimeMillis());
        getManagement().submitTask(getManagement().getDeploymentPlannerId(), scaleServiceTask);
    }

    private void execute() {
        super.execute(getManagement().getDeploymentPlannerId());
    }

    private Iterable<URI> getStateIdsStartingWith(final URI uri) {
        return Iterables.filter(
                getManagement().getStateReader().getElementIdsStartingWith(uri),
                new Predicate<URI>() {

                    @Override
                    public boolean apply(URI stateId) {
                        return stateId.toString().endsWith("/");
                    }
                });
    }


    private Iterable<URI> getAgentIds() {
        return getStateIdsStartingWith(StreamUtils.newURI(getManagement().getStateServerUri() + "agents/"));
    }

}
