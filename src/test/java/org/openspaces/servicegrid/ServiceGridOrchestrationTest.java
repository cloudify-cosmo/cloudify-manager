package org.openspaces.servicegrid;

import java.lang.reflect.Method;
import java.net.URI;
import java.net.URISyntaxException;
import java.text.DecimalFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.mock.MockAgent;
import org.openspaces.servicegrid.mock.MockManagement;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.mock.MockTaskContainer;
import org.openspaces.servicegrid.mock.MockTaskContainerParameter;
import org.openspaces.servicegrid.mock.TaskConsumerRegistrar;
import org.openspaces.servicegrid.service.ServiceUtils;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlan;
import org.openspaces.servicegrid.service.state.ServiceGridPlannerState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleServiceTask;
import org.openspaces.servicegrid.service.tasks.UninstallServiceTask;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.openspaces.servicegrid.time.MockCurrentTimeProvider;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;
import org.testng.log.TextFormatter;

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Ordering;
import com.google.common.collect.Sets;

public class ServiceGridOrchestrationTest {
	
	private final Logger logger;
	private MockManagement management;
	private Set<MockTaskContainer> containers;
	private MockCurrentTimeProvider timeProvider;
	private TaskConsumerRegistrar taskConsumerRegistrar;
	
	public ServiceGridOrchestrationTest() {
		logger = Logger.getLogger(this.getClass().getName());
		setSimpleLoggerFormatter(logger);
	}

	@BeforeMethod
	public void before(Method method) {
		
		timeProvider = new MockCurrentTimeProvider();
		containers =  Sets.newSetFromMap(new ConcurrentHashMap<MockTaskContainer, Boolean>());
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
		
		management = new MockManagement(taskConsumerRegistrar, timeProvider);
		management.registerTaskConsumers();
		logger.info("Starting " + method.getName());
	}
	
	@AfterMethod
	public void after() {
		logAllTasks();
	}
	
	/**
	 * Tests deployment of 1 instance
	 */
	@Test
	public void installSingleInstanceServiceTest() {
		installService("tomcat", 1);
		execute();
		assertSingleServiceInstance("tomcat");
	}

	/**
	 * Tests deployment of 2 instances
	 */
	@Test
	public void installMultipleInstanceServiceTest() {
		installService("tomcat", 2);
		execute();
		assertTwoTomcatInstances();
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
		assertServiceInstalledWithOneInstance("tomcat");
		Assert.assertEquals(getAgentState(getAgentId(0)).getProgress(), AgentState.Progress.AGENT_STARTED);
		Assert.assertEquals(getAgentState(getAgentId(1)).getProgress(), AgentState.Progress.MACHINE_TERMINATED);
		Assert.assertEquals(getServiceInstanceState(getServiceInstanceId("tomcat", 0)).getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		Assert.assertEquals(getServiceInstanceState(getServiceInstanceId("tomcat", 1)).getProgress(), ServiceInstanceState.Progress.INSTANCE_STOPPED);
	}
	
	/**
	 * Tests uninstalling tomcat service
	 */
	@Test
	public void uninstallServiceTest() {
		installService("tomcat",1);
		execute();
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
	
	private void assertTomcatUninstalledGracefully() {
		boolean instanceUnreachable = false;
		assertTomcatUninstalled(instanceUnreachable);
	}
	
	private void assertTomcatUninstalledUnreachable() {
		boolean instanceUnreachable = true;
		assertTomcatUninstalled(instanceUnreachable);
	}
	
	private void assertTomcatUninstalled(boolean instanceUnreachable) {
		Assert.assertEquals(getDeploymentPlannerState().getDeploymentPlan().getServices().size(), 0);
		final ServiceState serviceState = getServiceState(getServiceId("tomcat"));
		Assert.assertEquals(serviceState.getInstanceIds().size(), 0);
		Assert.assertEquals(serviceState.getProgress(), ServiceState.Progress.SERVICE_UNINSTALLED);
		
		ServiceInstanceState instanceState = getServiceInstanceState(Iterables.getOnlyElement(getServiceInstanceIds("tomcat")));
		if (instanceUnreachable) {
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_UNREACHABLE);
		}
		else {
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STOPPED);
		}
		AgentState agentState = getAgentState(Iterables.getOnlyElement(getAgentIds()));
		Assert.assertEquals(agentState.getProgress(), AgentState.Progress.MACHINE_TERMINATED);
	}
	
	/**
	 * Tests management state recovery from crash
	 */
	@Test
	public void managementRestartTest() {
		installService("tomcat", 1);
		execute();
		logAllTasks();
		restartManagement();
		execute();
		assertSingleServiceInstance("tomcat");
	}
	
	/**
	 * Tests management state recovery from crash when one of the agents also failed.
	 * This test is similar to scaleOut test. Since there is one agent, and the plan is two agents.
	 */
	@Test
	public void managementRestartAndOneAgentRestartTest() {
		installService("tomcat", 2);
		execute();
		logAllTasks();
		restartAgent(getAgentId(1));
		restartManagement();
		execute();
		 
		assertTwoTomcatInstances(expectedAgentZeroNotRestartedAgentOneRestarted(), expectedBothMachinesNotRestarted());
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
		Assert.assertEquals(getDeploymentPlannerState().getDeploymentPlan().getServices().size(), 1);
		Assert.assertEquals(Iterables.size(getAgentIds()), 1);
		Assert.assertEquals(Iterables.size(getServiceInstanceIds(serviceName)),1);
		assertServiceInstalledWithOneInstance(serviceName, numberOfAgentRestarts, numberOfMachineRestarts);
	}

	private void assertServiceInstalledWithOneInstance(
			String serviceName, int numberOfAgentRestarts, int numberOfMachineRestarts) {
		final URI serviceId = getServiceId(serviceName);
		final ServiceState serviceState = getServiceState(serviceId);
		Assert.assertEquals(serviceState.getProgress(), ServiceState.Progress.SERVICE_INSTALLED);
		final URI instanceId = Iterables.getOnlyElement(serviceState.getInstanceIds());
		final ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
		final URI agentId = instanceState.getAgentId();
		Assert.assertEquals(instanceState.getServiceId(), serviceId);
		Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		
		final AgentState agentState = getAgentState(agentId);
		Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()),instanceId);
		Assert.assertEquals(agentState.getProgress(), AgentState.Progress.AGENT_STARTED);
		Assert.assertEquals(agentState.getNumberOfAgentRestarts(), numberOfAgentRestarts);
		Assert.assertEquals(agentState.getNumberOfMachineRestarts(), numberOfMachineRestarts);
		
		final ServiceGridPlannerState plannerState = getDeploymentPlannerState();
		final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId().get(agentId)), instanceId);
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId().get(serviceId)), instanceId);
		final ServiceConfig serviceConfig = deploymentPlan.getServiceById(serviceId); 
		Assert.assertEquals(serviceConfig.getServiceId(), serviceId);
	}

	private ServiceGridPlannerState getDeploymentPlannerState() {
		return StreamUtils.getLastElement(getStateReader(), management.getDeploymentPlannerId(), ServiceGridPlannerState.class);
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
		Assert.assertEquals(serviceState.getProgress(), ServiceState.Progress.SERVICE_INSTALLED);
		Iterable<URI> instanceIds = getStateIdsStartingWith(newURI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),2);
		
		final ServiceGridPlannerState plannerState = getDeploymentPlannerState();
		final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceId(), serviceId);
		Assert.assertEquals(Iterables.size(deploymentPlan.getInstanceIdsByServiceId().get(serviceId)), 2);
		
		Iterable<URI> agentIds = getAgentIds();
		int numberOfAgents = Iterables.size(agentIds);
		Assert.assertEquals(numberOfAgents, 2);
		for (int i = 0 ; i < numberOfAgents; i++) {
			
			URI agentId = Iterables.get(agentIds, i);
			AgentState agentState = getAgentState(agentId);
			Assert.assertEquals(agentState.getProgress(), AgentState.Progress.AGENT_STARTED);
			Assert.assertEquals(agentState.getNumberOfAgentRestarts(), (int) numberOfAgentRestartsPerAgent.get(agentId));
			Assert.assertEquals(agentState.getNumberOfMachineRestarts(), (int) numberOfMachineRestartsPerAgent.get(agentId));
			URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
			Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
			ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
			Assert.assertEquals(instanceState.getServiceId(), serviceId);
			Assert.assertEquals(instanceState.getAgentId(), agentId);
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
			Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId().get(agentId)), instanceId);
		}
		
	}

	private ServiceState getServiceState(final URI serviceId) {
		ServiceState serviceState = StreamUtils.getLastElement(getStateReader(), serviceId, ServiceState.class);
		Assert.assertNotNull(serviceState, "No state for " + serviceId);
		return serviceState;
	}

	private AgentState getAgentState(URI agentId) {
		return getLastState(agentId, AgentState.class);
	}
	
	private ServiceInstanceState getServiceInstanceState(URI instanceId) {
		return getLastState(instanceId, ServiceInstanceState.class);
	}
	
	private <T extends TaskConsumerState> T getLastState(URI executorId, Class<T> stateClass) {
		T lastState = StreamUtils.getLastElement(getStateReader(), executorId, stateClass);
		Assert.assertNotNull(lastState);
		return lastState;
	}

	private void installService(String name, int numberOfInstances) {
		ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setDisplayName(name);
		serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
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
	
	private void submitTask(final URI target, final Task installServiceTask) {
		installServiceTask.setSourceTimestamp(timeProvider.currentTimeMillis());
		Preconditions.checkNotNull(target);
		Preconditions.checkNotNull(installServiceTask);
		installServiceTask.setTarget(target);
		((MockStreams<Task>)management.getTaskReader()).addElement(target, installServiceTask);
	}

	private void scaleService(String serviceName, int plannedNumberOfInstances) {
		final ScaleServiceTask scaleServiceTask = new ScaleServiceTask();
		URI serviceId = getServiceId(serviceName);
		scaleServiceTask.setServiceId(serviceId);
		scaleServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
		scaleServiceTask.setSourceTimestamp(timeProvider.currentTimeMillis());
		submitTask(management.getDeploymentPlannerId(), scaleServiceTask);
	}

	
	private URI getServiceId(String name) {
		return newURI("http://localhost/services/" + name + "/");
	}
	
	private void execute() {
		
		int consecutiveEmptyCycles = 0;
		for (; timeProvider.currentTimeMillis() < 1000000; timeProvider.increaseBy(1000 - (timeProvider.currentTimeMillis() % 1000))) {

			boolean emptyCycle = true;
			{
			TaskProducerTask producerTask = new TaskProducerTask();
			producerTask.setMaxNumberOfSteps(100);
			submitTask(management.getDeploymentPlannerId(), producerTask);
			}
			{
			timeProvider.increaseBy(1);
			TaskProducerTask producerTask = new TaskProducerTask();
			producerTask.setMaxNumberOfSteps(100);
			submitTask(management.getOrchestratorId(), producerTask);
			}
			
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
	
	private Iterable<URI> getServiceInstanceIds(String serviceName) {
		return getStateIdsStartingWith(newURI("http://localhost/services/"+serviceName+"/instances/"));
	}
	
	private URI getServiceInstanceId(final String serviceName, final int index) {
		return newURI("http://localhost/services/"+serviceName+"/instances/"+index+"/");
	}

	private Iterable<URI> getStateIdsStartingWith(URI uri) {
		final Iterable<URI> instanceIds = ((MockStreams<TaskConsumerState>)getStateReader()).getElementIdsStartingWith(uri);
		return instanceIds;
	}
	
	private Iterable<URI> getTaskIdsStartingWith(URI uri) {
		final Iterable<URI> instanceIds = ((MockStreams<Task>)management.getTaskReader()).getElementIdsStartingWith(uri);
		return instanceIds;
	}

	private Iterable<URI> getAgentIds() {
		return getStateIdsStartingWith(newURI("http://localhost/agent/"));
	}
	
	private URI getAgentId(final int index) {
		return newURI("http://localhost/agent/"+index+"/");
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
		Preconditions.checkState(agentState.getProgress().equals(AgentState.Progress.AGENT_STARTED));
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

	private Iterable<Task> getSortedTasks() {
	
		List<Task> tasks = Lists.newArrayList(); 
		final Iterable<URI> taskConsumerIds = getTaskIdsStartingWith(newURI("http://localhost/"));
		StreamReader<Task> taskReader = management.getTaskReader();
		for (final URI taskConsumerId : taskConsumerIds) {
			Set<URI> ignore = ImmutableSet.copyOf(ServiceUtils.getExecutingAndPendingTasks(management.getStateReader(), taskReader, taskConsumerId));
			for (URI taskId = taskReader.getFirstElementId(taskConsumerId); taskId != null ; taskId = taskReader.getNextElementId(taskId)) {
				if (!ignore.contains(taskId)) {
					final Task task = taskReader.getElement(taskId, Task.class);
					tasks.add(task);
				}
			}
		}

		Ordering<Task> ordering = new Ordering<Task>() {
			@Override
			public int compare(Task o1, Task o2) {
				int c;
				if (o1.getSourceTimestamp() == null) c = 1;
				else if (o2.getSourceTimestamp() == null) c = -1;
				else {
					c = o1.getSourceTimestamp().compareTo(o2.getSourceTimestamp());
				}
				return c;
			}
		};

		return ordering.sortedCopy(tasks);
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

	private void logAllTasks() {
		final Iterable<Task> tasks = getSortedTasks();
		for (final Task task : tasks) {
			final DecimalFormat timestampFormatter = new DecimalFormat("###,###");
			final Long sourceTimestamp = task.getSourceTimestamp();
			String timestamp = "";
			if (sourceTimestamp != null) {
				timestamp = timestampFormatter.format(sourceTimestamp);
			}
			if (logger.isLoggable(Level.INFO)) {
				String impersonatedTarget = "";
				if (task instanceof ImpersonatingTask) {
					ImpersonatingTask impersonatingTask = (ImpersonatingTask) task;
					impersonatedTarget = "impersonated: " + impersonatingTask.getImpersonatedTarget();
				}
				logger.info(String.format("%-8s%-32starget: %-50s%-50s",timestamp,task.getClass().getSimpleName(),task.getTarget(), impersonatedTarget));
			}
		}
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

	public StreamReader<TaskConsumerState> getStateReader() {
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
