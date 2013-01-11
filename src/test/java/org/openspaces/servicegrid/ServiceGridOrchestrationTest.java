package org.openspaces.servicegrid;

import java.lang.reflect.Method;
import java.net.URI;
import java.net.URISyntaxException;
import java.text.DecimalFormat;
import java.util.List;
import java.util.Set;
import java.util.logging.Logger;

import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.client.ServiceClient;
import org.openspaces.servicegrid.client.ServiceClientParameter;
import org.openspaces.servicegrid.mock.MockMachineProvisioner;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.mock.MockTaskContainer;
import org.openspaces.servicegrid.mock.MockTaskContainerParameter;
import org.openspaces.servicegrid.mock.TaskConsumerRegistrar;
import org.openspaces.servicegrid.service.OrchestrateTask;
import org.openspaces.servicegrid.service.ServiceGridOrchestrator;
import org.openspaces.servicegrid.service.ServiceGridOrchestratorParameter;
import org.openspaces.servicegrid.service.ServiceGridPlanner;
import org.openspaces.servicegrid.service.ServiceGridPlannerParameter;
import org.openspaces.servicegrid.service.ServiceUtils;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleOutServiceTask;
import org.openspaces.servicegrid.time.MockCurrentTimeProvider;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;
import org.testng.log.TextFormatter;

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Ordering;
import com.google.common.collect.Sets;

public class ServiceGridOrchestrationTest {
	
	private final Logger logger;
	private ServiceClient client;
	private Set<MockTaskContainer> containers;
	private final URI orchestratorId;
	private final URI floorPlannerId;
	private final URI machineProvisionerId;
	private MockStreams<TaskConsumerState> state;
	private MockStreams<Task> taskBroker;
	private MockCurrentTimeProvider timeProvider;
	
	public ServiceGridOrchestrationTest() throws URISyntaxException {
		logger = Logger.getLogger(this.getClass().getName());
		setSimpleLoggerFormatter(logger);
		
		orchestratorId = new URI("http://localhost/services/orchestrator/");
		floorPlannerId = new URI("http://localhost/services/floorPlanner/");
		machineProvisionerId = new URI("http://localhost/services/provisioner/");
	}

	@BeforeMethod
	public void before(Method method) {
		
		timeProvider = new MockCurrentTimeProvider();
		state = new MockStreams<TaskConsumerState>();
		taskBroker = new MockStreams<Task>();
		client = newServiceClient();
		containers = Sets.newCopyOnWriteArraySet();
		addContainers(
				newOrchestratorContainer(),				
				newFloorPlannerContainer(),
				newMachineProvisionerContainer()
		);
		logger.info("Starting " + method.getName());
	}
	
	@AfterMethod
	public void after() throws URISyntaxException {
		logAllTasks();
	}
	
	@Test
	public void installSingleInstanceServiceTest() throws URISyntaxException {
		installService("tomcat", 1);
		execute();
		assertSingleTomcatInstance();
	}
		
	@Test
	public void installMultipleInstanceServiceTest() throws URISyntaxException {
		installService("tomcat", 2);
		execute();
		assertTwoTomcatInstances();
	}
	
	
	@Test
	public void agentFailoverTest() throws URISyntaxException {
		installService("tomcat", 1);
		execute();
		killOnlyAgent();
		execute();
		URI instanceId = getOnlyServiceInstanceId();
		ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
		Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		AgentState agentState = getAgentState(getOnlyAgentId());
		Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()),instanceId);
		Assert.assertEquals(agentState.getProgress(),AgentState.Progress.AGENT_STARTED);
		Assert.assertEquals(agentState.getNumberOfRestarts(),1);
	}
	
	@Test
	public void scaleOutServiceTest() throws URISyntaxException {
		installService("tomcat", 1);
		execute();
		scaleOutService("tomcat",2);
		execute();
		assertTwoTomcatInstances();
	}

	private void assertSingleTomcatInstance() throws URISyntaxException {
		URI serviceId = getServiceId("tomcat");
		final ServiceState serviceState = state.getElement(state.getLastElementId(serviceId), ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()),1);
		//logger.info("URIs: " + state.getElementIdsStartingWith(new URI("http://localhost/")));
		URI instanceId = getOnlyServiceInstanceId();
		URI agentId = getOnlyAgentId();
		ServiceInstanceState instanceState = getServiceInstanceState(instanceId);
		Assert.assertEquals(instanceState.getServiceId(), serviceId);
		Assert.assertEquals(instanceState.getAgentId(), agentId);
		Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		
		AgentState agentState = getAgentState(agentId);
		Assert.assertEquals(Iterables.getOnlyElement(agentState.getServiceInstanceIds()),instanceId);
		Assert.assertEquals(agentState.getProgress(), AgentState.Progress.AGENT_STARTED);
		Assert.assertEquals(agentState.getNumberOfRestarts(), 0);
	}

	private URI getOnlyAgentId() throws URISyntaxException {
		return Iterables.getOnlyElement(getAgentIds());
	}
	
	private void assertTwoTomcatInstances() throws URISyntaxException {
		final URI serviceId = getServiceId("tomcat");
		final ServiceState serviceState = state.getElement(state.getLastElementId(serviceId), ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()),2);
		//logger.info("URIs: " + state.getElementIdsStartingWith(new URI("http://localhost/")));
		Iterable<URI> instanceIds = state.getElementIdsStartingWith(new URI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),2);
		
		Iterable<URI> agentIds = getAgentIds();
		int numberOfAgents = Iterables.size(agentIds);
		Assert.assertEquals(numberOfAgents, 2);
		for (int i = 0 ; i < numberOfAgents; i++) {
			
			URI agentId = Iterables.get(agentIds, i);
			AgentState agentState = getAgentState(agentId);
			Assert.assertEquals(agentState.getProgress(), AgentState.Progress.AGENT_STARTED);
			Assert.assertEquals(agentState.getNumberOfRestarts(), 0);
			URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
			Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
			ServiceInstanceState instanceState = state.getElement(state.getLastElementId(instanceId), ServiceInstanceState.class);
			Assert.assertEquals(instanceState.getServiceId(), serviceId);
			Assert.assertEquals(instanceState.getAgentId(), agentId);
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		}
	}
		
	
	/*public void installTwoSingleInstanceServicesTest(){
		installService("tomcat", 1);
		installService("cassandra", 1);
		execute();
	}*/
	
//	public void uninstallSingleInstanceServiceTest(){
//		installService(1);
//		execute();
//		
//	}

	private AgentState getAgentState(URI agentId) {
		return getLastState(agentId, AgentState.class);
	}
	
	private ServiceInstanceState getServiceInstanceState(URI instanceId) throws URISyntaxException {
		return getLastState(instanceId, ServiceInstanceState.class);
	}
	
	private <T extends TaskConsumerState> T getLastState(URI executorId, Class<T> stateClass) {
		T lastState = ServiceUtils.getLastState(state, executorId, stateClass);
		Assert.assertNotNull(lastState);
		return lastState;
	}

	private void installService(String name, int numberOfInstances) throws URISyntaxException {
		ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setDisplayName(name);
		serviceConfig.setPlannedNumberOfInstances(numberOfInstances);
		serviceConfig.setServiceId(getServiceId(name));
		final InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setServiceConfig(serviceConfig);
		submitTask(installServiceTask);
	}

	private void submitTask(final Task installServiceTask) {
		installServiceTask.setSourceTimestamp(timeProvider.currentTimeMillis());
		client.addServiceTask(orchestratorId, installServiceTask);
		timeProvider.increaseBy(1000);
	}

	private void scaleOutService(String serviceName, int plannedNumberOfInstances) throws URISyntaxException {
		final ScaleOutServiceTask scaleOutServiceTask = new ScaleOutServiceTask();
		URI serviceId = getServiceId(serviceName);
		scaleOutServiceTask.setServiceId(serviceId);
		scaleOutServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
		scaleOutServiceTask.setSourceTimestamp(timeProvider.currentTimeMillis());
		submitTask(scaleOutServiceTask);
	}

	
	private URI getServiceId(String name) throws URISyntaxException {
		return new URI("http://localhost/services/" + name + "/");
	}
	
	private void execute() throws URISyntaxException {
		
		int consecutiveEmptyCycles = 0;
		for (; timeProvider.currentTimeMillis() < 300000; timeProvider.increaseBy(1000)) {

			boolean emptyCycle = true;
			OrchestrateTask orchestrateTask = new OrchestrateTask();
			orchestrateTask.setMaxNumberOfSteps(100);
			submitTask(orchestrateTask);
			
			for (MockTaskContainer container : containers) {
				Assert.assertEquals(container.getExecutorId().getHost(),"localhost");
				while (container.consumeNextTask()) {
					if (!container.getExecutorId().equals(orchestratorId)) {
						emptyCycle = false;
					}
				}
			}

			if (emptyCycle) {
				consecutiveEmptyCycles++;
			}

			if (consecutiveEmptyCycles > 60) {
				return;
			}
		}
		StringBuilder sb = new StringBuilder();
		Iterable<URI> servicesIds = state.getElementIdsStartingWith(new URI("http://services/"));
		for (URI URI : servicesIds) {
			ServiceState serviceState = state.getElement(state.getLastElementId(URI), ServiceState.class);
			sb.append("service: " + serviceState.getServiceConfig().getDisplayName());
			sb.append(" - ");
			for (URI instanceURI : serviceState.getInstanceIds()) {
				ServiceInstanceState instanceState = state.getElement(state.getLastElementId(instanceURI), ServiceInstanceState.class);
				sb.append(instanceURI).append("[").append(instanceState.getProgress()).append("] ");
			}
			
		}
		
		Assert.fail("Executing too many cycles progress=" + sb);
	}
	
	private URI getOnlyServiceInstanceId() throws URISyntaxException {
		final Iterable<URI> instanceIds = state.getElementIdsStartingWith(new URI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),1);
		
		final URI serviceInstanceId = Iterables.getOnlyElement(instanceIds);
		return serviceInstanceId;
	}

	private Iterable<URI> getAgentIds() throws URISyntaxException {
		return state.getElementIdsStartingWith(new URI("http://localhost/agent/"));
	}

	private void killOnlyAgent() throws URISyntaxException {
		killAgent(getOnlyAgentId());
	}
	
	private void killAgent(URI agentId) {
		for (MockTaskContainer container : containers) {
			if (container.getExecutorId().equals(agentId)) {
				//logger.info("Killed agent " + agentId);
				container.kill();
				return;
			}
		}
		Assert.fail("Failed to kill agent " + agentId);
	}
	
	private Iterable<Task> getSortedTasks() throws URISyntaxException {
	
		List<Task> tasks = Lists.newArrayList(); 
		final Iterable<URI> taskConsumerIds = taskBroker.getElementIdsStartingWith(new URI("http://localhost/"));
		for (final URI executorId : taskConsumerIds) {
			for (URI taskId = taskBroker.getFirstElementId(executorId); taskId != null ; taskId = taskBroker.getNextElementId(taskId)) {
				final Task task = taskBroker.getElement(taskId, Task.class);
				tasks.add(task);
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
	private ServiceClient newServiceClient() {
		final ServiceClientParameter serviceClientParameter = new ServiceClientParameter();
		serviceClientParameter.setStateReader(state);
		serviceClientParameter.setTaskReader(taskBroker);
		serviceClientParameter.setTaskWriter(taskBroker);
		return new ServiceClient(serviceClientParameter);
	}

	private MockTaskContainer newOrchestratorContainer() {
		
		final ServiceGridOrchestratorParameter serviceOrchestratorParameter = new ServiceGridOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorId(orchestratorId);
		serviceOrchestratorParameter.setMachineProvisionerId(machineProvisionerId);
		serviceOrchestratorParameter.setFloorPlannerId(floorPlannerId);
		serviceOrchestratorParameter.setTaskConsumer(taskBroker);
		serviceOrchestratorParameter.setStateReader(state);
		serviceOrchestratorParameter.setTimeProvider(timeProvider);
	
		ServiceGridOrchestrator taskConsumer = new ServiceGridOrchestrator(serviceOrchestratorParameter);
		return newContainer(orchestratorId, taskConsumer);
	}

	private MockTaskContainer newFloorPlannerContainer() {
		
		final ServiceGridPlannerParameter servicePlannerParameter = new ServiceGridPlannerParameter();
		servicePlannerParameter.setFloorPlannerExecutorId(floorPlannerId);
		servicePlannerParameter.setStateReader(state);
		servicePlannerParameter.setTimeProvider(timeProvider);
		
		ServiceGridPlanner taskConsumer = new ServiceGridPlanner(servicePlannerParameter);
		return newContainer(floorPlannerId, taskConsumer);
	}

	private MockTaskContainer newMachineProvisionerContainer() {
		
		TaskConsumerRegistrar taskConsumerRegistrar = new TaskConsumerRegistrar() {
			
			@Override
			public void registerTaskConsumer(
					final Object taskConsumer, final URI executorId) {
				
				MockTaskContainer container = newContainer(executorId, taskConsumer);
				addContainer(container);
			}

			@Override
			public void unregisterTaskConsumer(final URI executorId) {
				containers.remove(
					Iterables.find(containers, new Predicate<MockTaskContainer>() {
						@Override
						public boolean apply(MockTaskContainer executor) {
							return executorId.equals(executor.getExecutorId());
						}
					})
				);
			}

		};

		MockMachineProvisioner taskConsumer = new MockMachineProvisioner(taskConsumerRegistrar); 
		return newContainer(machineProvisionerId, taskConsumer);
	}
	
	private void addContainers(MockTaskContainer ... newContainers) {
		for (MockTaskContainer  container : newContainers) {
			addContainer(container);
		}
	}
	
	private void addContainer(MockTaskContainer container) {
		//logger.info("Adding container for " + container.getExecutorId());
		Preconditions.checkState(!containers.contains(container), "Container " + container.getExecutorId() + " was already added");
		containers.add(container);
	}
	
	private void logAllTasks() throws URISyntaxException {
		final Iterable<Task> tasks = getSortedTasks();
		for (final Task task : tasks) {
			final DecimalFormat timestampFormatter = new DecimalFormat("###,###");
			final Long sourceTimestamp = task.getSourceTimestamp();
			String timestamp = "";
			if (sourceTimestamp != null) {
				timestamp = timestampFormatter.format(sourceTimestamp);
			}
			logger.info(String.format("%-8s%-30starget: %s",timestamp,task.getClass().getSimpleName(),task.getTarget()));
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
		containerParameter.setStateReader(state);
		containerParameter.setStateWriter(state);
		containerParameter.setTaskReader(taskBroker);
		containerParameter.setTaskWriter(taskBroker);
		containerParameter.setTimeProvider(timeProvider);
		return new MockTaskContainer(containerParameter);
	}

}
