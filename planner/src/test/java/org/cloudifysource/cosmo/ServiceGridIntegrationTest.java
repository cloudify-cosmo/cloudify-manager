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
import org.cloudifysource.cosmo.mock.MockAgent;
import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.mock.MockPlannerManagement;
import org.cloudifysource.cosmo.mock.MockTaskContainer;
import org.cloudifysource.cosmo.mock.MockTaskContainerParameter;
import org.cloudifysource.cosmo.mock.TaskConsumerRegistrar;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.time.MockCurrentTimeProvider;
import org.junit.AfterClass;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.agent.tasks.StartAgentTask;
import org.cloudifysource.cosmo.agent.tasks.StartMachineTask;
import org.cloudifysource.cosmo.service.state.*;
import org.cloudifysource.cosmo.service.tasks.*;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.state.StateReader;
import org.testng.Assert;
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

public class ServiceGridIntegrationTest {
	
	private final Logger logger;
	private MockPlannerManagement management;
	private Set<MockTaskContainer> containers;
	private MockCurrentTimeProvider timeProvider;
	private long startTimestamp;
	private TaskConsumerRegistrar taskConsumerRegistrar;
		
	public ServiceGridIntegrationTest() {
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
		uninstallService("tomcat");
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
		assertSingleServiceInstance("tomcat", numberOfAgentRestarts,numberOfMachineRestarts);
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
	 * Tests uninstalling tomcat service when machine hosting service instance failed.
	 */
	@Test
	public void killMachineUninstallServiceTest() {
		installService("tomcat",1);
		execute();
		killOnlyMachine();
		uninstallService("tomcat");
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
		restartManagement();
		execute();
		assertOneTomcatInstance();
		uninstallService("tomcat");
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
		restartAgent(getAgentId(1));
		restartManagement();
		execute();
		assertTwoTomcatInstances(expectedAgentZeroNotRestartedAgentOneRestarted(), expectedBothMachinesNotRestarted());
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
		assertServiceInstalledWithOneInstance("tomcat");
		assertServiceInstalledWithOneInstance("cassandra");
		Assert.assertEquals(Iterables.size(getServiceInstanceIds("tomcat")),1);
		Assert.assertEquals(Iterables.size(getServiceInstanceIds("cassandra")),1);
		uninstallService("tomcat");
		uninstallService("cassandra");
		execute();
		assertTomcatUninstalledGracefully();
	}

	@Test
	public void scalingRulesTest() {
		
		installService("tomcat", 1);
		final ServiceScalingRule rule = new ServiceScalingRule();
		rule.setPropertyName("request-throughput");
		rule.setLowThreshold(1);
		rule.setHighThreshold(10);
		scalingrule("tomcat", rule);
		execute();
		
		assertOneTomcatInstance();
		final URI instanceId0 = getServiceInstanceId("tomcat", 0);
		setServiceInstanceProperty(instanceId0, "request-throughput", 100);
		execute();
		assertTwoTomcatInstances();
		final URI instanceId1 = getServiceInstanceId("tomcat", 1);
		setServiceInstanceProperty(instanceId0, "request-throughput", 0);
		setServiceInstanceProperty(instanceId1, "request-throughput", 0);
		execute();
		assertTomcatScaledInFrom2To1();
		uninstallService("tomcat");
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
		URI instanceId = getServiceInstanceId("tomcat", 0);
		setServiceInstanceProperty(instanceId, propertyName, propertyValue);
		execute();
		Assert.assertEquals(getServiceInstanceProperty(propertyName, instanceId), propertyValue);
		uninstallService("tomcat");
		execute();
		assertTomcatUninstalledGracefully();
	}

	private Object getServiceInstanceProperty(final String propertyName, URI instanceId) {
		return getServiceInstanceState(instanceId).getProperty(propertyName);
	}

	private void setServiceInstanceProperty(
			URI instanceId,
			String propertyName, 
			Object propertyValue) {
		
		SetInstancePropertyTask task = new SetInstancePropertyTask();
		task.setStateId(instanceId);
		task.setPropertyName(propertyName);
		task.setPropertyValue(propertyValue);
		
		final URI agentId = getServiceInstanceState(instanceId).getAgentId();
		submitTask(agentId, task);
	}

	private void assertOneTomcatInstance() {
		assertSingleServiceInstance("tomcat");
	}
	
	private void assertTomcatScaledInFrom2To1() {
		assertServiceInstalledWithOneInstance("tomcat");
		Assert.assertTrue(getAgentState(getAgentId(0)).isProgress(AgentState.Progress.AGENT_STARTED));
		Assert.assertTrue(getAgentState(getAgentId(1)).isProgress(AgentState.Progress.MACHINE_TERMINATED));
		Assert.assertTrue(getServiceInstanceState(getServiceInstanceId("tomcat", 0)).isProgress("service_started"));
		Assert.assertTrue(getServiceInstanceState(getServiceInstanceId("tomcat", 1)).isProgress("service_uninstalled"));
	}

	private void scalingrule(String serviceName, ServiceScalingRule rule) {
		rule.setServiceId(getServiceId(serviceName));
		ScalingRulesTask task = new ScalingRulesTask();
		task.setScalingRule(rule);
		submitTask(management.getCapacityPlannerId(), task);
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
		final URI serviceId = getServiceId("tomcat");
		Assert.assertFalse(getDeploymentPlannerState().getDeploymentPlan().isServiceExists(serviceId));
		final ServiceState serviceState = getServiceState(serviceId);
		Assert.assertEquals(serviceState.getInstanceIds().size(), 0);
		Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_UNINSTALLED));
		
		for (URI instanceId: getServiceInstanceIds("tomcat")) {
			ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
			if (instanceUnreachable) {
				Assert.assertTrue(instanceState.isUnreachable());
			}
			else {
				Assert.assertTrue(instanceState.isProgress("service_uninstalled"));
			}
			URI agentId = instanceState.getAgentId();
			AgentState agentState = getAgentState(agentId);
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
		assertSingleServiceInstance(serviceName, zeroAgentRestarts,zeroMachineRestarts);
	}
	
	private void assertSingleServiceInstance(String serviceName, int numberOfAgentRestarts, int numberOfMachineRestarts) {
		Assert.assertNotNull(getDeploymentPlannerState());
		Assert.assertEquals(getDeploymentPlannerState().getDeploymentPlan().getServices().size(), 1);
		Assert.assertEquals(Iterables.size(getAgentIds()), 1, "Expected 1 agent id, instead found: "+ getAgentIds());
		Assert.assertEquals(Iterables.size(getServiceInstanceIds(serviceName)),1);
		assertServiceInstalledWithOneInstance(serviceName, numberOfAgentRestarts, numberOfMachineRestarts);
	}

	private void assertServiceInstalledWithOneInstance(
			String serviceName, int numberOfAgentRestarts, int numberOfMachineRestarts) {
		final URI serviceId = getServiceId(serviceName);
		final ServiceState serviceState = getServiceState(serviceId);
		Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
		final URI instanceId = Iterables.getOnlyElement(serviceState.getInstanceIds());
		final ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
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
		
		final AgentState agentState = getAgentState(agentId);
		Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()),instanceId);
		Assert.assertTrue(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
		Assert.assertEquals(agentState.getNumberOfAgentRestarts(), numberOfAgentRestarts);
		Assert.assertEquals(agentState.getNumberOfMachineRestarts(), numberOfMachineRestarts);

		TaskConsumerHistory agentTasksHistory = getTasksHistory(agentId);
		Assert.assertEquals(Iterables.size(Iterables.filter(agentTasksHistory.getTasksHistory(),StartMachineTask.class)),1+numberOfMachineRestarts);
		Assert.assertEquals(Iterables.size(Iterables.filter(agentTasksHistory.getTasksHistory(),StartAgentTask.class)),1+numberOfMachineRestarts);

		
		final ServiceGridDeploymentPlannerState plannerState = getDeploymentPlannerState();
		final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId(serviceId)), instanceId);
		final ServiceConfig serviceConfig = deploymentPlan.getServiceById(serviceId).getServiceConfig(); 
		Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
	}

	private TaskConsumerHistory getTasksHistory(final URI stateId) {
		final URI tasksHistoryId = ServiceUtils.toTasksHistoryId(stateId);
		EtagState<TaskConsumerHistory> etagState = getStateReader().get(tasksHistoryId, TaskConsumerHistory.class);
		Preconditions.checkNotNull(etagState);
		return etagState.getState(); 
	}

	private ServiceGridDeploymentPlannerState getDeploymentPlannerState() {
		return getStateReader().get(management.getDeploymentPlannerId(), ServiceGridDeploymentPlannerState.class).getState();
	}

	private URI getOnlyAgentId() {
		return Iterables.getOnlyElement(getAgentIds());
	}
	
	private void assertTwoTomcatInstances() {
		
		assertTwoTomcatInstances(expectedBothAgentsNotRestarted(), expectedBothMachinesNotRestarted());
	}
	
	private void assertTwoTomcatInstances(Map<URI,Integer> numberOfAgentRestartsPerAgent, Map<URI,Integer> numberOfMachineRestartsPerAgent) {
		final URI serviceId = getServiceId("tomcat");
		final ServiceState serviceState = getServiceState(serviceId);
		Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()),2);
		Assert.assertTrue(serviceState.isProgress(ServiceState.Progress.SERVICE_INSTALLED));
		Iterable<URI> instanceIds = getStateIdsStartingWith(newURI(management.getStateServerUri()+"services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),2);
		
		final ServiceGridDeploymentPlannerState plannerState = getDeploymentPlannerState();
		final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceConfig().getServiceId(), serviceId);
		Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId(serviceId)), 2);
		
		Iterable<URI> agentIds = getAgentIds();
		int numberOfAgents = Iterables.size(agentIds);
		Assert.assertEquals(numberOfAgents, 2);
		for (int i = 0 ; i < numberOfAgents; i++) {
			
			URI agentId = Iterables.get(agentIds, i);
			AgentState agentState = getAgentState(agentId);
			Assert.assertTrue(agentState.isProgress(AgentState.Progress.AGENT_STARTED));
			Assert.assertEquals(agentState.getNumberOfAgentRestarts(), (int) numberOfAgentRestartsPerAgent.get(agentId));
			Assert.assertEquals(agentState.getNumberOfMachineRestarts(), (int) numberOfMachineRestartsPerAgent.get(agentId));
			URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
			Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
			ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
			Assert.assertEquals(instanceState.getServiceId(), serviceId);
			Assert.assertEquals(instanceState.getAgentId(), agentId);
			Assert.assertTrue(instanceState.isProgress("service_started"));
			Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId(agentId)), instanceId);
		}
		
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
		return newURI(management.getStateServerUri()+"services/" + name + "/");
	}
	
	private void execute() {
		
		int consecutiveEmptyCycles = 0;
		for (; timeProvider.currentTimeMillis() < startTimestamp + 1000000; timeProvider.increaseBy(1000 - (timeProvider.currentTimeMillis() % 1000))) {

			boolean emptyCycle = true;
			
			submitTaskProducerTask(management.getCapacityPlannerId());
			timeProvider.increaseBy(1);
			submitTaskProducerTask(management.getDeploymentPlannerId());
			timeProvider.increaseBy(1);
			submitTaskProducerTask(management.getOrchestratorId());

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
	
	private Iterable<URI> getServiceInstanceIds(String serviceName) {
		return getStateIdsStartingWith(newURI(management.getStateServerUri()+"services/"+serviceName+"/instances/"));
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

	private void killOnlyMachine() {
		killMachine(getOnlyAgentId());
	}
	
	private void restartOnlyAgent() {
		restartAgent(getOnlyAgentId());
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
	 * This method simulates an unexpected crash of a machine 
	 */
	private void killMachine(URI agentId) {
		findContainer(agentId).killMachine();
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
