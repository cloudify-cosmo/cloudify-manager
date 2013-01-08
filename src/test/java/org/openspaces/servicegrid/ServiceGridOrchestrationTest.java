package org.openspaces.servicegrid;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Comparator;
import java.util.Set;
import java.util.logging.Logger;

import org.openspaces.servicegrid.client.ServiceClient;
import org.openspaces.servicegrid.mock.MockEmbeddedAgentLifecycleTaskExecutor;
import org.openspaces.servicegrid.mock.MockImmediateMachineSpawnerTaskExecutor;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.mock.MockTaskContainer;
import org.openspaces.servicegrid.mock.TaskExecutorWrapper;
import org.openspaces.servicegrid.model.service.InstallServiceTask;
import org.openspaces.servicegrid.model.service.ServiceGridOrchestratorState;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceState;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.MockCurrentTimeProvider;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Multiset;
import com.google.common.collect.Sets;
import com.google.common.collect.TreeMultiset;

public class ServiceGridOrchestrationTest {
	
	private ServiceClient client;
	private Set<MockTaskContainer> containers;
	private URI orchestratorExecutorId;
	private MockTaskContainer orchestratorContainer;
	private MockStreams<TaskExecutorState> state;
	private StreamConsumer<Task> taskConsumer;
	private final Logger logger = Logger.getLogger(this.getClass().getName());
	private MockStreams<Task> taskBroker;
	
	@BeforeMethod
	public void before() {
		
		final URI cloudExecutorId;
		final URI agentLifecycleExecutorId;
		
		try {
			orchestratorExecutorId = new URI("http://localhost/services/orchestrator/");
			cloudExecutorId = new URI("http://localhost/services/cloud/");
			agentLifecycleExecutorId = new URI("http://localhost/services/agentLifecycle/");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
		
		state = new MockStreams<TaskExecutorState>();
		StreamProducer<TaskExecutorState> stateWriter = state;
		StreamConsumer<TaskExecutorState> stateReader = state;
	
		this.taskBroker = new MockStreams<Task>();
		StreamProducer<Task> taskProducer = taskBroker;
		taskConsumer = taskBroker;
		
		stateWriter.addElement(orchestratorExecutorId, new ServiceGridOrchestratorState());
	
		client = new ServiceClient(stateReader, taskConsumer, taskProducer);
				
		final MockCurrentTimeProvider orchestratorTimeProvider = new MockCurrentTimeProvider();
		final ServiceOrchestratorParameter serviceOrchestratorParameter = new ServiceOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorExecutorId(orchestratorExecutorId);
		serviceOrchestratorParameter.setCloudExecutorId(cloudExecutorId);
		serviceOrchestratorParameter.setAgentLifecycleExecutorId(agentLifecycleExecutorId);
		serviceOrchestratorParameter.setTaskConsumer(taskConsumer);
		serviceOrchestratorParameter.setTaskProducer(taskProducer);
		serviceOrchestratorParameter.setStateReader(stateReader);
		serviceOrchestratorParameter.setTimeProvider(orchestratorTimeProvider);
	
		orchestratorContainer = new MockTaskContainer(
				orchestratorExecutorId,
				stateReader, stateWriter, 
				taskConsumer, 
				new ServiceGridOrchestrator(
						serviceOrchestratorParameter),
				orchestratorTimeProvider);

		containers = Sets.newCopyOnWriteArraySet();
		addContainers(
				orchestratorContainer,				
				new MockTaskContainer(
						cloudExecutorId, 
						stateReader, stateWriter,
						taskConsumer, 
						new MockImmediateMachineSpawnerTaskExecutor(),
						new MockCurrentTimeProvider()),
						
				new MockTaskContainer(
						agentLifecycleExecutorId, 
						stateReader, stateWriter,
						taskConsumer, 
						new MockEmbeddedAgentLifecycleTaskExecutor(new TaskExecutorWrapper() {
							
							@Override
							public void wrapTaskExecutor(
									Object taskExecutor, URI executorId) {
								
								MockTaskContainer container = new MockTaskContainer(executorId, state, state, taskConsumer, taskExecutor, new MockCurrentTimeProvider());
								addContainer(container);
							}

						}
						),
						new MockCurrentTimeProvider())
		);
	}
	
	private void addContainers(MockTaskContainer ... newContainers) {
		for (MockTaskContainer  container : newContainers) {
			addContainer(container);
		}
	}
	
	private void addContainer(MockTaskContainer container) {
		logger.info("Adding container for " + container.getExecutorId());
		containers.add(container);
	}
	
	@AfterMethod
	public void after() throws URISyntaxException {
		Iterable<Task> tasks = filterOrchestratorTasks(getSortedTasks());
		for (final Task task : tasks) {
			logger.info(task.getSourceTimestamp() + " target: " + task.getTarget() + " type:"+task.getClass());
		}
	}

	Iterable<Task> filterOrchestratorTasks(Iterable<Task> unfiltered) {
		return Iterables.filter(unfiltered, new Predicate<Task>(){

			@Override
			public boolean apply(Task task) {
				return orchestratorExecutorId.equals(task.getSource());
			}});
	}
	
	private Iterable<Task> getSortedTasks() throws URISyntaxException {
		final Iterable<URI> taskExecutorIds = taskBroker.getElementIdsStartingWith(new URI("http://localhost/"));
		Multiset<Task> sortedTasks = TreeMultiset.create(
				new Comparator<Task>() {

			@Override
			public int compare(Task o1, Task o2) {
				if (o1.getSourceTimestamp() == null) return 1;
				if (o2.getSourceTimestamp() == null) return -1;
				return o1.getSourceTimestamp().compareTo(o2.getSourceTimestamp());
			}
		});
		for (final URI taskExecutorId : taskExecutorIds) {
			for (URI taskId = taskBroker.getFirstElementId(taskExecutorId); taskId != null ; taskId = taskBroker.getNextElementId(taskId)) {
				final Task task = taskBroker.getElement(taskId, Task.class);
				sortedTasks.add(task);
			}
		}
		return sortedTasks;
	}
	
	@Test
	public void installSingleInstanceServiceTest() throws URISyntaxException {
		logger.info("Starting installSingleInstanceServiceTest URIs: " + state.getElementIdsStartingWith(new URI("http://localhost/")));
		installService("tomcat", 1);
		execute();
		final ServiceState serviceState = state.getElement(state.getLastElementId(getServiceURI("tomcat")), ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstancesIds()),1);
		logger.info("URIs: " + state.getElementIdsStartingWith(new URI("http://localhost/")));
		ServiceInstanceState instanceState = getOnlyServiceInstanceState();
		Assert.assertEquals(instanceState.getDisplayName(), "tomcat");
		Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		
		Assert.assertEquals(instanceState.getAgentExecutorId(),getOnlyAgentId());
	}

	private URI getOnlyAgentId() throws URISyntaxException {
		return Iterables.getOnlyElement(getAgentIds());
	}
	
	@Test
	public void installMultipleInstanceServiceTest() throws URISyntaxException {
		logger.info("Starting installMultipleInstanceServiceTest");
		installService("tomcat", 2);
		execute();
		
		final ServiceState serviceState = state.getElement(state.getLastElementId(getServiceURI("tomcat")), ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstancesIds()),2);
		logger.info("URIs: " + state.getElementIdsStartingWith(new URI("http://localhost/")));
		Iterable<URI> instanceIds = state.getElementIdsStartingWith(new URI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),2);
		
		Iterable<URI> agentIds = getAgentIds();
		Assert.assertEquals(Iterables.size(agentIds), 2);
		for (URI URI : instanceIds) {
			ServiceInstanceState instanceState = state.getElement(state.getLastElementId(URI), ServiceInstanceState.class);
			Assert.assertEquals(instanceState.getDisplayName(), "tomcat");
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
			Assert.assertTrue(Iterables.contains(agentIds, instanceState.getAgentExecutorId()));
		}
	}
	
	@Test
	public void agentFailoverTest() throws URISyntaxException {
		logger.info("Starting agentFailoverTest");
		installService("tomcat", 1);
		execute();
		killOnlyAgent();
		execute();
		Assert.assertEquals(getOnlyServiceInstanceState().getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		Iterable<URI> agentIds = getAgentIds();
		Assert.assertEquals(Iterables.size(agentIds),2);
		URI secondAgentId = Iterables.get(agentIds, 1);
		Assert.assertEquals(getOnlyServiceInstanceState().getAgentExecutorId(),secondAgentId);	
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


	private void installService(String name, int numberOfInstances) throws URISyntaxException {
		ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setDisplayName(name);
		serviceConfig.setNumberOfInstances(numberOfInstances);
		serviceConfig.setServiceId(getServiceURI(name));
		final InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setServiceConfig(serviceConfig);
		client.addServiceTask(orchestratorExecutorId, installServiceTask);
	}

	private URI getServiceURI(String name) throws URISyntaxException {
		return new URI("http://localhost/services/" + name);
	}
	
	private void execute() throws URISyntaxException {

		int consecutiveEmptyCycles = 0;
		for (int i = 0 ; i < 120 ;) {

			boolean emptyCycle = true;
			OrchestrateTask orchestrateTask = new OrchestrateTask();
			orchestrateTask.setMaxNumberOfOrchestrationSteps(100);
			client.addServiceTask(orchestratorExecutorId, orchestrateTask);
			
			for (MockTaskContainer container : containers) {
				Assert.assertEquals(container.getExecutorId().getHost(),"localhost");
				while (container.stepTaskExecutor()) {
					if (!container.getExecutorId().equals(orchestratorExecutorId)) {
						emptyCycle = false;
					}
					i++;
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
			for (URI instanceURI : serviceState.getInstancesIds()) {
				ServiceInstanceState instanceState = state.getElement(state.getLastElementId(instanceURI), ServiceInstanceState.class);
				sb.append(instanceURI).append("[").append(instanceState.getProgress()).append("] ");
			}
			
		}
		
		Assert.fail("Executing too many cycles progress=" + sb);
	}

	private ServiceInstanceState getOnlyServiceInstanceState() throws URISyntaxException {
		Iterable<URI> instanceIds = state.getElementIdsStartingWith(new URI("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),1);
		
		ServiceInstanceState instanceState = state.getElement(state.getLastElementId(Iterables.getOnlyElement(instanceIds)), ServiceInstanceState.class);
		return instanceState;
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
				logger.info("Killed agent " + agentId);
				container.kill();
				return;
			}
		}
		Assert.fail("Failed to kill agent " + agentId);
	}
}
