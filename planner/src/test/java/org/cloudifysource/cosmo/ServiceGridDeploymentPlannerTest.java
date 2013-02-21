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

import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Iterables;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.mock.MockAgent;
import org.cloudifysource.cosmo.mock.MockPlannerManagement;
import org.cloudifysource.cosmo.mock.MockTaskContainer;
import org.cloudifysource.cosmo.mock.MockTaskContainerParameter;
import org.cloudifysource.cosmo.mock.TaskConsumerRegistrar;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.state.ServiceConfig;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlannerState;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceScalingRule;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.service.tasks.InstallServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScaleServiceTask;
import org.cloudifysource.cosmo.service.tasks.ScalingRulesTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
import org.cloudifysource.cosmo.service.tasks.UninstallServiceTask;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.time.MockCurrentTimeProvider;
import org.testng.Assert;
import org.testng.annotations.AfterClass;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;
import org.testng.log.TextFormatter;

import java.lang.reflect.Method;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

public class ServiceGridDeploymentPlannerTest {

    private final Logger logger;
    private MockPlannerManagement management;
    private Set<MockTaskContainer> containers;
    private MockCurrentTimeProvider timeProvider;
    private long startTimestamp;
    private TaskConsumerRegistrar taskConsumerRegistrar;

    public ServiceGridDeploymentPlannerTest() {
        logger = Logger.getLogger(this.getClass().getName());
        setSimpleLoggerFormatter(logger);
    }

    @BeforeClass
    public void beforeClass() {

        containers =  Sets.newSetFromMap(new ConcurrentHashMap<MockTaskContainer, Boolean>());
        timeProvider = new MockCurrentTimeProvider(startTimestamp);
        taskConsumerRegistrar = new TaskConsumerRegistrar() {

            @Override
            public void registerTaskConsumer(
                    final Object taskConsumer, final URI taskConsumerId) {

                MockTaskContainer container = newContainer(taskConsumerId, taskConsumer);
                addContainer(container);
            }

            @Override
            public Object unregisterTaskConsumer(final URI taskConsumerId) {
                MockTaskContainer mockTaskContainer = findContainer(taskConsumerId);
                boolean removed = containers.remove(mockTaskContainer);
                Preconditions.checkState(removed, "Failed to remove container " + taskConsumerId);
                return mockTaskContainer.getTaskConsumer();
            }
        };

        management = new MockPlannerManagement(taskConsumerRegistrar, timeProvider);
    }

    @BeforeMethod
    public void beforeMethod(Method method) {

        startTimestamp = System.currentTimeMillis();
        timeProvider.setCurrentTimeMillis(startTimestamp);
        management.start();
        logger.info("Starting " + method.getName());
    }

    @AfterMethod(alwaysRun=true)
    public void afterMethod(Method method) {

        try {
            management.unregisterTaskConsumers();
            final Function<MockTaskContainer, URI> getContainerIdFunc = new Function<MockTaskContainer, URI>() {

                @Override
                public URI apply(MockTaskContainer input) {
                    return input.getTaskConsumerId();
                }
            };

            Assert.assertEquals(containers.size(), 0, "Cleanup failure in test " + method.getName() + ":"+ Iterables.toString(Iterables.transform(containers, getContainerIdFunc)));

        }
        finally {
            containers.clear();
        }
    }

    @AfterClass
    public void afterClass() {
        management.close();
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
        uninstallService("tomcat");
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
        uninstallService("tomcat");
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
        uninstallService("tomcat");
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
        scaleService("tomcat",1);
        execute();
        assertTomcatScaledInFrom2To1();
        uninstallService("tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Tests management state recovery from crash
     */
    @Test
    public void managementRestartTest() {
        installService("tomcat", 1);
        execute();
        restartManagement();
        execute();
        assertOneTomcatInstance();
        uninstallService("tomcat");
        execute();
        assertTomcatUninstalledGracefully();
    }

    /**
     * Install two services, each with one instance
     */
    @Test
    public void installTwoSingleInstanceServicesTest(){
        installService("tomcat", 1);
        installService("cassandra", 1);
        execute();
        assertServiceInstalledWithOneInstance("tomcat", 0);
        assertServiceInstalledWithOneInstance("cassandra", 1);
        uninstallService("tomcat");
        uninstallService("cassandra");
        execute();
        assertTomcatUninstalledGracefully();
    }

    private void assertOneTomcatInstance() {
        assertSingleServiceInstance("tomcat");
    }

    private void assertTomcatScaledInFrom2To1() {
        assertServiceInstalledWithOneInstance("tomcat");
    }

    private void assertTomcatUninstalledGracefully() {
        final URI serviceId = getServiceId("tomcat");
        Assert.assertFalse(getDeploymentPlannerState().getDeploymentPlan().isServiceExists(serviceId));
    }

    private void assertServiceInstalledWithOneInstance(String serviceName) {
        assertServiceInstalledWithOneInstance(serviceName, 0);
    }

    private void assertSingleServiceInstance(String serviceName) {
        final int zeroAgentRestarts = 0;
        final int zeroMachineRestarts = 0;
        assertSingleServiceInstance(serviceName, zeroAgentRestarts,zeroMachineRestarts);
    }

    private void assertSingleServiceInstance(String serviceName, int numberOfAgentRestarts, int numberOfMachineRestarts) {
        Assert.assertNotNull(getDeploymentPlannerState());
        Assert.assertEquals(getDeploymentPlannerState().getDeploymentPlan().getServices().size(), 1);
    }

    private void assertServiceInstalledWithOneInstance(
            String serviceName, int agentIndex) {
        final URI serviceId = getServiceId(serviceName);
        final URI instanceId = ServiceUtils.newInstanceId(serviceId, 0);
        final URI agentId = ServiceUtils.newAgentId(management.getAgentsId(), agentIndex);
        final ServiceGridDeploymentPlannerState plannerState = getDeploymentPlannerState();
        final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId(serviceId)), instanceId);
        final ServiceConfig serviceConfig = deploymentPlan.getServiceById(serviceId).getServiceConfig();
        Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
    }

    private ServiceGridDeploymentPlannerState getDeploymentPlannerState() {
        return getStateReader().get(management.getDeploymentPlannerId(), ServiceGridDeploymentPlannerState.class).getState();
    }

    private void assertTwoTomcatInstances() {

        assertTwoTomcatInstances(expectedBothAgentsNotRestarted(), expectedBothMachinesNotRestarted());
    }

    private void assertTwoTomcatInstances(Map<URI,Integer> numberOfAgentRestartsPerAgent, Map<URI,Integer> numberOfMachineRestartsPerAgent) {
        final URI serviceId = getServiceId("tomcat");

        final ServiceGridDeploymentPlannerState plannerState = getDeploymentPlannerState();
        final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
        Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
        Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);
    }

    private ServiceState getServiceState(final URI serviceId) {
        ServiceState serviceState = getStateReader().get(serviceId, ServiceState.class).getState();
        Assert.assertNotNull(serviceState, "No state for " + serviceId);
        return serviceState;
    }

    private AgentState getAgentState(URI agentId) {
        return getLastState(agentId, AgentState.class);
    }

    private ServiceInstanceState getServiceInstanceState(URI instanceId) {
        return getLastState(instanceId, ServiceInstanceState.class);
    }

    private <T extends TaskConsumerState> T getLastState(URI taskConsumerId, Class<T> stateClass) {
        EtagState<T> etagState = getStateReader().get(taskConsumerId, stateClass);
        Preconditions.checkNotNull(etagState);
        T lastState = etagState.getState();
        Assert.assertNotNull(lastState);
        return lastState;
    }

    private void installService(String name, int numberOfInstances) {
        final int minNumberOfInstances = 1;
        final int maxNumberOfInstances = 2;
        ServiceConfig serviceConfig = new ServiceConfig();
        serviceConfig.setDisplayName(name);
        serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
        serviceConfig.setMaxNumberOfInstances(maxNumberOfInstances);
        serviceConfig.setMinNumberOfInstances(minNumberOfInstances);
        serviceConfig.setServiceId(getServiceId(name));
        final InstallServiceTask installServiceTask = new InstallServiceTask();
        installServiceTask.setServiceConfig(serviceConfig);
        submitTask(management.getDeploymentPlannerId(), installServiceTask);
    }

    private void uninstallService(String name) {
        URI serviceId = getServiceId(name);
        final UninstallServiceTask uninstallServiceTask = new UninstallServiceTask();
        uninstallServiceTask.setServiceId(serviceId);
        submitTask(management.getDeploymentPlannerId(), uninstallServiceTask);
    }

    private void submitTask(final URI target, final Task task) {
        task.setProducerTimestamp(timeProvider.currentTimeMillis());
        task.setProducerId(newURI(management.getStateServerUri()+"webui"));
        task.setConsumerId(target);
        management.getTaskWriter().postNewTask(task);
    }

    private void scaleService(String serviceName, int plannedNumberOfInstances) {
        final ScaleServiceTask scaleServiceTask = new ScaleServiceTask();
        URI serviceId = getServiceId(serviceName);
        scaleServiceTask.setServiceId(serviceId);
        scaleServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
        scaleServiceTask.setProducerTimestamp(timeProvider.currentTimeMillis());
        submitTask(management.getDeploymentPlannerId(), scaleServiceTask);
    }

    private URI getServiceId(String name) {
        return ServiceUtils.newServiceId(management.getStateServerUri(), name);
    }

    private void execute() {

        int consecutiveEmptyCycles = 0;
        for (; timeProvider.currentTimeMillis() < startTimestamp + 1000000; timeProvider.increaseBy(1000 - (timeProvider.currentTimeMillis() % 1000))) {

            boolean emptyCycle = true;

            submitTaskProducerTask(management.getDeploymentPlannerId());

            for (MockTaskContainer container : containers) {
                Preconditions.checkState(containers.contains(container));
                Assert.assertEquals(container.getTaskConsumerId().getHost(),"localhost");
                Task task = null;

                for(timeProvider.increaseBy(1); (task = container.consumeNextTask()) != null; timeProvider.increaseBy(1)) {
                    if (!(task instanceof TaskProducerTask) && !(task instanceof PingAgentTask)) {
                        emptyCycle = false;
                    }
                }
            }

            if (emptyCycle) {
                consecutiveEmptyCycles++;
            }
            else {
                consecutiveEmptyCycles = 0;
            }

            if (consecutiveEmptyCycles > 60) {
                return;
            }
        }
        StringBuilder sb = new StringBuilder();
        Iterable<URI> servicesIds;
        try {
            servicesIds = getStateIdsStartingWith(new URI("http://services/"));
        } catch (URISyntaxException e) {
            throw Throwables.propagate(e);
        }
        for (URI serviceId : servicesIds) {
            ServiceState serviceState = getServiceState(serviceId);
            sb.append("service: " + serviceState.getServiceConfig().getDisplayName());
            sb.append(" - ");
            for (URI instanceId : serviceState.getInstanceIds()) {
                ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
                sb.append(instanceId).append("[").append(instanceState.getProgress()).append("] ");
            }

        }

        Assert.fail("Executing too many cycles progress=" + sb);
    }

    private void submitTaskProducerTask(final URI taskProducerId) {
        final TaskProducerTask producerTask = new TaskProducerTask();
        producerTask.setMaxNumberOfSteps(100);
        submitTask(taskProducerId, producerTask);
    }

    private URI getServiceInstanceId(final String serviceName, final int index) {
        return newURI(management.getStateServerUri()+"services/"+serviceName+"/instances/"+index+"/");
    }

    private Iterable<URI> getStateIdsStartingWith(final URI uri) {
        return Iterables.filter(
                getStateReader().getElementIdsStartingWith(uri),
                new Predicate<URI>(){

                    @Override
                    public boolean apply(URI stateId) {
                        return stateId.toString().endsWith("/");
                    }});
    }


    private Iterable<URI> getAgentIds() {
        return getStateIdsStartingWith(newURI(management.getStateServerUri()+"agents/"));
    }

    private URI getAgentId(final int index) {
        return newURI(management.getStateServerUri()+"agents/"+index+"/");
    }

    /**
     * This method simulates failure of the agent, and immediate restart by a reliable watchdog
     * running on the same machine
     */
    private void restartAgent(URI agentId) {

        MockAgent agent = (MockAgent) taskConsumerRegistrar.unregisterTaskConsumer(agentId);
        AgentState agentState = agent.getState();
        Preconditions.checkState(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
        agentState.setNumberOfAgentRestarts(agentState.getNumberOfAgentRestarts() +1);
        taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
    }

    /**
     * This method simulates the crash of all management processes
     * and their automatic start by a reliable watchdog running on the same machine
     */
    private void restartManagement() {
        management.restart();
    }

    private MockTaskContainer findContainer(final URI agentId) {
        MockTaskContainer container = Iterables.tryFind(containers, new Predicate<MockTaskContainer>() {

            @Override
            public boolean apply(MockTaskContainer container) {
                return agentId.equals(container.getTaskConsumerId());
            }
        }).orNull();

        Preconditions.checkNotNull(container, "Cannot find container for %s", agentId);
        return container;
    }

    private URI newURI(String uri) {
        try {
            return new URI(uri);
        } catch (URISyntaxException e) {
            throw Throwables.propagate(e);
        }
    }

    private void addContainer(MockTaskContainer container) {
        //logger.info("Adding container for " + container.getExecutorId());
        Preconditions.checkState(findContainserById(container.getTaskConsumerId()) == null, "Container " + container.getTaskConsumerId() + " was already added");
        containers.add(container);
    }

    private MockTaskContainer findContainserById(final URI id) {
        return Iterables.find(containers, new Predicate<MockTaskContainer>(){

            @Override
            public boolean apply(MockTaskContainer container) {
                return id.equals(container.getTaskConsumerId());
            }}, null);
    }


    private static void setSimpleLoggerFormatter(final Logger logger) {
        Logger parentLogger = logger;
        while (parentLogger.getHandlers().length == 0) {
            parentLogger = logger.getParent();
        }

        parentLogger.getHandlers()[0].setFormatter(new TextFormatter());
    }

    private MockTaskContainer newContainer(
            URI executorId,
            Object taskConsumer) {
        MockTaskContainerParameter containerParameter = new MockTaskContainerParameter();
        containerParameter.setExecutorId(executorId);
        containerParameter.setTaskConsumer(taskConsumer);
        containerParameter.setStateReader(management.getStateReader());
        containerParameter.setStateWriter(management.getStateWriter());
        containerParameter.setTaskReader(management.getTaskReader());
        containerParameter.setTaskWriter(management.getTaskWriter());
        containerParameter.setPersistentTaskReader(management.getPersistentTaskReader());
        containerParameter.setPersistentTaskWriter(management.getPersistentTaskWriter());
        containerParameter.setTimeProvider(timeProvider);
        return new MockTaskContainer(containerParameter);
    }

    public StateReader getStateReader() {
        return management.getStateReader();
    }

    private ImmutableMap<URI, Integer> expectedBothAgentsNotRestarted() {
        return ImmutableMap.<URI,Integer>builder()
                .put(getAgentId(0), 0)
                .put(getAgentId(1), 0)
                .build();
    }

    private ImmutableMap<URI, Integer> expectedBothMachinesNotRestarted() {
        return ImmutableMap.<URI,Integer>builder()
                .put(getAgentId(0), 0)
                .put(getAgentId(1), 0)
                .build();
    }

    private ImmutableMap<URI, Integer> expectedAgentZeroNotRestartedAgentOneRestarted() {
        return ImmutableMap.<URI,Integer>builder()
                .put(getAgentId(0), 0)
                .put(getAgentId(1), 1)
                .build();
    }
}
