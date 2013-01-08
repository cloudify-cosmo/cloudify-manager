package org.openspaces.servicegrid;

import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNotNull;
import static org.testng.Assert.assertTrue;
import static org.testng.Assert.fail;

import java.net.URI;
import java.net.URISyntaxException;

import org.openspaces.servicegrid.client.ServiceClient;
import org.openspaces.servicegrid.mock.MockCloudMachineTaskExecutor;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.mock.MockTaskContainer;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.InstallServiceTask;
import org.openspaces.servicegrid.model.service.ServiceGridOrchestratorState;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceState;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.MockCurrentTimeProvider;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;

public class InstallServiceTest {

	private static final MockCurrentTimeProvider timeProvider = new MockCurrentTimeProvider();
	private StreamProducer<TaskExecutorState> stateWriter;
	private StreamConsumer<TaskExecutorState> stateReader;
	
	private StreamProducer<Task> taskProducer;
	private StreamConsumer<Task> taskConsumer;
	
	private ServiceClient client;
	
	private final URI orchestratorExecutorId;
	private ServiceGridOrchestrator orchestrator; 
	private MockTaskContainer orchestratorContainer;
	
	private MockTaskContainer cloudContainer;
	private MockCloudMachineTaskExecutor cloudExecutor;
	private final URI cloudExecutorId;
	private final URI agentLifecycleExecutorId;
	
	public InstallServiceTest() {
		try {
			orchestratorExecutorId = new URI("http://localhost/services/tomcat/");
			cloudExecutorId = new URI("http://localhost/services/cloud");
			agentLifecycleExecutorId = new URI("http://localhost/services/agentLifecycle");
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}
	
	@BeforeMethod
	public void before() {
		MockStreams<TaskExecutorState> state = new MockStreams<TaskExecutorState>();
		stateWriter = state;
		stateReader = state;
		
		MockStreams<Task> taskBroker = new MockStreams<Task>();
		taskProducer = taskBroker;
		taskConsumer = taskBroker;
		stateWriter.addElement(orchestratorExecutorId, new ServiceGridOrchestratorState());
		orchestrator = new ServiceGridOrchestrator(createServiceOrchestratorParameter());
		cloudExecutor = new MockCloudMachineTaskExecutor();
		
		client = new ServiceClient(stateReader, taskConsumer, taskProducer);
		orchestratorContainer = new MockTaskContainer(orchestratorExecutorId, stateReader, stateWriter, taskConsumer, orchestrator, timeProvider);
		cloudContainer = new MockTaskContainer(cloudExecutorId, stateReader, stateWriter, taskConsumer, cloudExecutor, timeProvider);
	}

	private ServiceOrchestratorParameter createServiceOrchestratorParameter() {
		final ServiceOrchestratorParameter serviceOrchestratorParameter = new ServiceOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorExecutorId(orchestratorExecutorId);
		serviceOrchestratorParameter.setCloudExecutorId(cloudExecutorId);
		serviceOrchestratorParameter.setAgentLifecycleExecutorId(agentLifecycleExecutorId);
		serviceOrchestratorParameter.setTaskConsumer(taskConsumer);
		serviceOrchestratorParameter.setTaskProducer(taskProducer);
		serviceOrchestratorParameter.setStateReader(stateReader);
		serviceOrchestratorParameter.setTimeProvider(timeProvider);
		return serviceOrchestratorParameter;
	}
	
	@Test
	public void createServiceGetServiceStateTest() {
		
		assertTrue(Iterables.isEmpty(client.getExecutorState(orchestratorExecutorId, ServiceGridOrchestratorState.class).getServices()));
	}
	
	
	@Test
	public void installServiceStepExecutorTest() {
		
		installService();		
		assertTrue(Iterables.isEmpty(client.getExecutorState(orchestratorExecutorId, ServiceGridOrchestratorState.class).getServices()));
		orchestratorContainer.stepTaskExecutor();
		orchestrate();
		orchestrate();
		final ServiceState serviceState = getTomcatServiceState();
		assertEquals(serviceState.getServiceConfig().getDisplayName(), "tomcat");
	}

	private void installService() {
		final ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setDisplayName("tomcat");
		serviceConfig.setServiceId(newURI("http://localhost/services/tomcat/"));
		serviceConfig.setNumberOfInstances(1);
		
		final InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setServiceConfig(serviceConfig);
		final URI taskId = client.addServiceTask(orchestratorExecutorId, installServiceTask);
		assertTrue(client.getTask(taskId) instanceof InstallServiceTask);
	}
	
	private URI newURI(String uri){
		try {
			return new URI(uri);
		} catch (URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}
	
	@Test
	public void installServiceAlreadyInstalledTest() {
		
		installService();		
		orchestratorContainer.stepTaskExecutor();
		
		installService();
		try {
			orchestratorContainer.stepTaskExecutor();
			fail("Expected exception");
		}
		catch (IllegalStateException e) {
			
		}
	}
		
	@Test
	public void installServiceAndStartMachineTest() {
		
		installService();		
		orchestratorContainer.stepTaskExecutor();
		
		orchestrate();
		orchestratorContainer.stepTaskExecutor();
		orchestrate();
		orchestrate();
		orchestrate();
		
		cloudContainer.stepTaskExecutor();
		assertTrue(getLastTask(cloudExecutorId) instanceof StartMachineTask);
		
		assertEquals(getTomcatInstanceState().getProgress(), ServiceInstanceState.Progress.STARTING_MACHINE);
	}

	private Task getLastTask(URI executorId) {
		final TaskExecutorState cloudExecutorState = client.getExecutorState(executorId, TaskExecutorState.class);
		final URI taskId = cloudExecutorState.getLastCompletedTaskId();
		final Task lastCloudTask = client.getTask(taskId);
		return lastCloudTask;
	}

	private ServiceInstanceState getTomcatInstanceState() {
		final URI tomcatInstanceId = getTomcatInstanceId();
		final ServiceInstanceState tomcatInstanceState = client.getExecutorState(tomcatInstanceId, ServiceInstanceState.class);
		return tomcatInstanceState;
	}

	private URI getTomcatInstanceId() {
		final ServiceState tomcatState = getTomcatServiceState();
		final URI tomcatInstanceId = Iterables.getOnlyElement(tomcatState.getInstancesIds());
		return tomcatInstanceId;
	}

	private ServiceState getTomcatServiceState() {
		return client.getExecutorState(newURI("http://services/tomcat/"), ServiceState.class);
	}
	
	
	@Test
	public void installServiceAndStartAgentTest() {
		
		installService();		
		orchestratorContainer.stepTaskExecutor();
		
		orchestrate();
		orchestratorContainer.stepTaskExecutor();
		
		orchestrate();
		orchestrate();
		orchestrate();
		//Initiate machine creation
		cloudContainer.stepTaskExecutor();
		//Finish machine started on localhost
		cloudExecutor.signalLastStartedMachineFinished("localhost");		
		assertEquals(getTomcatInstanceState().getProgress(), ServiceInstanceState.Progress.MACHINE_STARTED);
		
		orchestrate();
		
		StartAgentTask lastElement = taskConsumer.getElement(taskConsumer.getLastElementId(agentLifecycleExecutorId), StartAgentTask.class);
		assertNotNull(lastElement.getAgentExecutorId());
		// make sure agent is installed on correct ip address
		assertEquals(lastElement.getIpAddress(), "localhost");
		
	}
	
	@Test
	public void installServiceAndCreateTomcatExecutorTest() {
		
		installService();		
		orchestratorContainer.stepTaskExecutor();		
		orchestrate();
		//Step for orchestrate of instance
		orchestratorContainer.stepTaskExecutor();
		
		orchestrate();
		orchestrate();
		orchestrate();
		//Initiate machine creation
		cloudContainer.stepTaskExecutor();
		//Finish machine started on localhost
		cloudExecutor.signalLastStartedMachineFinished("localhost");		
		orchestrate();
		
		//simulate implementation of StartAgentTask
		StartAgentTask lastAgentLifecycleTask = taskConsumer.getElement(taskConsumer.getLastElementId(agentLifecycleExecutorId), StartAgentTask.class);
		URI agentExecutorId = lastAgentLifecycleTask.getAgentExecutorId();
		ServiceInstanceState serviceInstanceState = 
				stateReader.getElement(stateReader.getLastElementId(getTomcatInstanceId()), ServiceInstanceState.class);
		serviceInstanceState.setAgentExecutorId(agentExecutorId);
		serviceInstanceState.setProgress(ServiceInstanceState.Progress.AGENT_STARTED);
		stateWriter.addElement(getTomcatInstanceId(), serviceInstanceState);
		
		orchestrate();

		// make sure agent is starting the correct tomcat instance executor
		InstallServiceInstanceTask lastAgentExecutorTask = 
				taskConsumer.getElement(taskConsumer.getLastElementId(agentExecutorId), InstallServiceInstanceTask.class);
		assertEquals(lastAgentExecutorTask.getImpersonatedTarget(), getTomcatInstanceId());
		
	}

	private void orchestrate() {
		client.addServiceTask(orchestratorExecutorId, new OrchestrateTask());
		orchestratorContainer.stepTaskExecutor();
	}

}
