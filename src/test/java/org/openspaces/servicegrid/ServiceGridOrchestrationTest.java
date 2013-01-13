package org.openspaces.servicegrid;

import java.lang.reflect.Method;
import java.net.URI;
import java.net.URISyntaxException;
import java.text.DecimalFormat;
import java.util.List;
import java.util.Set;
import java.util.logging.Logger;

import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.client.ServiceClient;
import org.openspaces.servicegrid.client.ServiceClientParameter;
import org.openspaces.servicegrid.mock.MockManagement;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.mock.MockTaskContainer;
import org.openspaces.servicegrid.mock.MockTaskContainerParameter;
import org.openspaces.servicegrid.mock.TaskConsumerRegistrar;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlan;
import org.openspaces.servicegrid.service.state.ServiceGridPlannerState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleOutServiceTask;
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
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Ordering;
import com.google.common.collect.Sets;

public class ServiceGridOrchestrationTest {
	
	private final Logger logger;
	private MockManagement management;
	private ServiceClient client;
	private Set<MockTaskContainer> containers;
	private MockCurrentTimeProvider timeProvider;
	private TaskConsumerRegistrar taskConsumerRegistrar;
	
	public ServiceGridOrchestrationTest() throws URISyntaxException {
		logger = Logger.getLogger(this.getClass().getName());
		setSimpleLoggerFormatter(logger);
	}

	@BeforeMethod
	public void before(Method method) {
		
		timeProvider = new MockCurrentTimeProvider();
		containers = Sets.newCopyOnWriteArraySet();
		taskConsumerRegistrar = new TaskConsumerRegistrar() {
			
			@Override
			public void registerTaskConsumer(
					final Object taskConsumer, final URI executorId) {
				
				MockTaskContainer container = newContainer(executorId, taskConsumer);
				addContainer(container);
			}

			@Override
			public void unregisterTaskConsumer(final URI executorId) {
				boolean removed = containers.remove(
					Iterables.find(containers, new Predicate<MockTaskContainer>() {
						@Override
						public boolean apply(MockTaskContainer executor) {
							return executorId.equals(executor.getExecutorId());
						}
					})
				);
				Preconditions.checkState(removed, "Failed to remove container " + executorId);
			}

		};
		
		management = new MockManagement(taskConsumerRegistrar, timeProvider);
		management.registerTaskConsumers();
		client = newServiceClient();
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

	@Test
	public void managementFailoverTest() throws URISyntaxException {
		installService("tomcat", 1);
		execute();
		management.restart();
		execute();
		assertSingleTomcatInstance();
	}
	
	private void assertSingleTomcatInstance() throws URISyntaxException {
		URI serviceId = getServiceId("tomcat");
		final ServiceState serviceState = StreamUtils.getLastElement(getStateReader(), serviceId, ServiceState.class);
		Assert.assertNotNull(serviceState, "No state for " + serviceId);
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
		
		final ServiceGridPlannerState plannerState = StreamUtils.getLastElement(getStateReader(), management.getDeploymentPlannerId(), ServiceGridPlannerState.class);
		final ServiceGridDeploymentPlan deploymentPlan = plannerState.getDeploymentPlan();
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId().get(agentId)), instanceId);
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByServiceId().get(serviceId)), instanceId);
		Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getServices()).getServiceId(), serviceId);
		
	}

	private URI getOnlyAgentId() throws URISyntaxException {
		return Iterables.getOnlyElement(getAgentIds());
	}
	
	private void assertTwoTomcatInstances() throws URISyntaxException {
		final URI serviceId = getServiceId("tomcat");
		final ServiceState serviceState = StreamUtils.getLastElement(getStateReader(), serviceId, ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstanceIds()),2);
		//logger.info("URIs: " + state.getElementIdsStartingWith(new URI("http://localhost/")));
		Iterable<URI> instanceIds = getStateIdsStartingWith(new URI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),2);
		
		final ServiceGridPlannerState plannerState = StreamUtils.getLastElement(getStateReader(), management.getDeploymentPlannerId(), ServiceGridPlannerState.class);
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
			Assert.assertEquals(agentState.getNumberOfRestarts(), 0);
			URI instanceId = Iterables.getOnlyElement(agentState.getServiceInstanceIds());
			Assert.assertTrue(Iterables.contains(instanceIds, instanceId));
			ServiceInstanceState instanceState = StreamUtils.getLastElement(getStateReader(), instanceId, ServiceInstanceState.class);
			Assert.assertEquals(instanceState.getServiceId(), serviceId);
			Assert.assertEquals(instanceState.getAgentId(), agentId);
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
			Assert.assertEquals(Iterables.getOnlyElement(deploymentPlan.getInstanceIdsByAgentId().get(agentId)), instanceId);
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
		T lastState = StreamUtils.getLastElement(getStateReader(), executorId, stateClass);
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
		submitTask(management.getDeploymentPlannerId(), installServiceTask);
	}

	private void submitTask(final URI target, final Task installServiceTask) {
		installServiceTask.setSourceTimestamp(timeProvider.currentTimeMillis());
		client.addServiceTask(target, installServiceTask);
		timeProvider.increaseBy(1000);
	}

	private void scaleOutService(String serviceName, int plannedNumberOfInstances) throws URISyntaxException {
		final ScaleOutServiceTask scaleOutServiceTask = new ScaleOutServiceTask();
		URI serviceId = getServiceId(serviceName);
		scaleOutServiceTask.setServiceId(serviceId);
		scaleOutServiceTask.setPlannedNumberOfInstances(plannedNumberOfInstances);
		scaleOutServiceTask.setSourceTimestamp(timeProvider.currentTimeMillis());
		submitTask(management.getDeploymentPlannerId(), scaleOutServiceTask);
	}

	
	private URI getServiceId(String name) throws URISyntaxException {
		return new URI("http://localhost/services/" + name + "/");
	}
	
	private void execute() throws URISyntaxException {
		
		int consecutiveEmptyCycles = 0;
		for (; timeProvider.currentTimeMillis() < 1000000; timeProvider.increaseBy(1000)) {

			boolean emptyCycle = true;
			{
			TaskProducerTask producerTask = new TaskProducerTask();
			producerTask.setMaxNumberOfSteps(100);
			submitTask(management.getDeploymentPlannerId(), producerTask);
			}
			{
			TaskProducerTask producerTask = new TaskProducerTask();
			producerTask.setMaxNumberOfSteps(100);
			submitTask(management.getOrchestratorId(), producerTask);
			}
			
			for (MockTaskContainer container : containers) {
				Assert.assertEquals(container.getExecutorId().getHost(),"localhost");
				Task task = null;
				while ((task = container.consumeNextTask()) != null) {
					if (!(task instanceof TaskProducerTask) && !(task instanceof PingAgentTask)) {
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
		Iterable<URI> servicesIds = getStateIdsStartingWith(new URI("http://services/"));
		for (URI serviceId : servicesIds) {
			ServiceState serviceState = StreamUtils.getLastElement(getStateReader(), serviceId, ServiceState.class);
			sb.append("service: " + serviceState.getServiceConfig().getDisplayName());
			sb.append(" - ");
			for (URI instanceURI : serviceState.getInstanceIds()) {
				ServiceInstanceState instanceState = StreamUtils.getLastElement(getStateReader(), instanceURI, ServiceInstanceState.class);
				sb.append(instanceURI).append("[").append(instanceState.getProgress()).append("] ");
			}
			
		}
		
		Assert.fail("Executing too many cycles progress=" + sb);
	}
	
	private URI getOnlyServiceInstanceId() throws URISyntaxException {
		final Iterable<URI> instanceIds = getStateIdsStartingWith(new URI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),1);
		
		final URI serviceInstanceId = Iterables.getOnlyElement(instanceIds);
		return serviceInstanceId;
	}

	private Iterable<URI> getStateIdsStartingWith(URI uri) {
		final Iterable<URI> instanceIds = ((MockStreams<TaskConsumerState>)getStateReader()).getElementIdsStartingWith(uri);
		return instanceIds;
	}
	
	private Iterable<URI> getTaskIdsStartingWith(URI uri) {
		final Iterable<URI> instanceIds = ((MockStreams<Task>)management.getTaskReader()).getElementIdsStartingWith(uri);
		return instanceIds;
	}

	private Iterable<URI> getAgentIds() throws URISyntaxException {
		return getStateIdsStartingWith(new URI("http://localhost/agent/"));
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
		final Iterable<URI> taskConsumerIds = getTaskIdsStartingWith(new URI("http://localhost/"));
		StreamReader<Task> taskReader = management.getTaskReader();
		for (final URI executorId : taskConsumerIds) {
			for (URI taskId = taskReader.getFirstElementId(executorId); taskId != null ; taskId = taskReader.getNextElementId(taskId)) {
				final Task task = taskReader.getElement(taskId, Task.class);
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
		serviceClientParameter.setStateReader(getStateReader());
		serviceClientParameter.setTaskReader(management.getTaskReader());
		serviceClientParameter.setTaskWriter(management.getTaskWriter());
		return new ServiceClient(serviceClientParameter);
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
		containerParameter.setStateReader(management.getStateReader());
		containerParameter.setStateWriter(management.getStateWriter());
		containerParameter.setTaskReader(management.getTaskReader());
		containerParameter.setTaskWriter(management.getTaskWriter());
		containerParameter.setTimeProvider(timeProvider);
		return new MockTaskContainer(containerParameter);
	}

	public StreamReader<TaskConsumerState> getStateReader() {
		return management.getStateReader();
	}

}
