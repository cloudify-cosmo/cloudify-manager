package org.openspaces.servicegrid;

import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNotNull;
import static org.testng.Assert.assertNull;
import static org.testng.Assert.assertTrue;
import static org.testng.Assert.fail;

import java.net.MalformedURLException;
import java.net.URL;

import org.openspaces.servicegrid.client.ServiceClient;
import org.openspaces.servicegrid.mock.MockCloudMachineTaskExecutor;
import org.openspaces.servicegrid.mock.MockStreams;
import org.openspaces.servicegrid.mock.MockTaskContainer;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.InstallServiceTask;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;

public class InstallServiceTest {

	private StreamProducer<TaskExecutorState> stateWriter;
	private StreamConsumer<TaskExecutorState> stateReader;
	
	private StreamProducer<Task> taskProducer;
	private StreamConsumer<Task> taskConsumer;
	
	private ServiceClient client;
	
	private final URL orchestratorExecutorId;
	private ServiceOrchestrator orchestrator; 
	private MockTaskContainer orchestratorContainer;
	
	private MockTaskContainer cloudContainer;
	private MockCloudMachineTaskExecutor cloudExecutor;
	private final URL cloudExecutorId;
	private final URL agentLifecycleExecutorId;
	
	public InstallServiceTest() {
		try {
			orchestratorExecutorId = new URL("http://localhost/services/tomcat/");
			cloudExecutorId = new URL("http://localhost/services/cloud");
			agentLifecycleExecutorId = new URL("http://localhost/services/agentLifecycle");
		} catch (MalformedURLException e) {
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
		stateWriter.addElement(orchestratorExecutorId, new ServiceOrchestratorState());
		orchestrator = new ServiceOrchestrator(createServiceOrchestratorParameter());
		cloudExecutor = new MockCloudMachineTaskExecutor();
		
		client = new ServiceClient(stateReader, taskConsumer, taskProducer);
		orchestratorContainer = new MockTaskContainer(orchestratorExecutorId, stateReader, stateWriter, taskConsumer, orchestrator);
		cloudContainer = new MockTaskContainer(cloudExecutorId, stateReader, stateWriter, taskConsumer, cloudExecutor);
	}

	private ServiceOrchestratorParameter createServiceOrchestratorParameter() {
		final ServiceOrchestratorParameter serviceOrchestratorParameter = new ServiceOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorExecutorId(orchestratorExecutorId);
		serviceOrchestratorParameter.setCloudExecutorId(cloudExecutorId);
		serviceOrchestratorParameter.setAgentLifecycleExecutorId(agentLifecycleExecutorId);
		serviceOrchestratorParameter.setTaskConsumer(taskConsumer);
		serviceOrchestratorParameter.setTaskProducer(taskProducer);
		serviceOrchestratorParameter.setStateReader(stateReader);
		return serviceOrchestratorParameter;
	}
	
	@Test
	public void createServiceGetServiceStateTest() {
		
		final ServiceOrchestratorState serviceState = getTomcatServiceState();
		assertNull(serviceState.getDisplayName());
	}
	
	
	@Test
	public void installServiceStepExecutorTest() {
		
		installService();		
		assertNull(client.getExecutorState(orchestratorExecutorId, ServiceOrchestratorState.class).getDisplayName());
		
		orchestratorContainer.stepTaskExecutor();
		final ServiceOrchestratorState serviceState = getTomcatServiceState();
		assertEquals(serviceState.getDisplayName(), "tomcat");
		URL taskId = serviceState.getLastCompletedTaskId();
		assertTrue(client.getTask(taskId) instanceof InstallServiceTask);
	}

	private void installService() {
		final InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setDisplayName("tomcat");
		final URL taskId = client.addServiceTask(orchestratorExecutorId, installServiceTask);
		assertTrue(client.getTask(taskId) instanceof InstallServiceTask);
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
		
		cloudContainer.stepTaskExecutor();
		assertTrue(getLastTask(cloudExecutorId) instanceof StartMachineTask);
		
		assertEquals(getTomcatInstanceState().getProgress(), ServiceInstanceState.Progress.STARTING_MACHINE);
	}

	private Task getLastTask(URL executorId) {
		final TaskExecutorState cloudExecutorState = client.getExecutorState(executorId, TaskExecutorState.class);
		final URL taskId = cloudExecutorState.getLastCompletedTaskId();
		final Task lastCloudTask = client.getTask(taskId);
		return lastCloudTask;
	}

	private ServiceInstanceState getTomcatInstanceState() {
		final URL tomcatInstanceId = getTomcatInstanceId();
		final ServiceInstanceState tomcatInstanceState = client.getExecutorState(tomcatInstanceId, ServiceInstanceState.class);
		return tomcatInstanceState;
	}

	private URL getTomcatInstanceId() {
		final ServiceOrchestratorState tomcatState = getTomcatServiceState();
		final URL tomcatInstanceId = Iterables.getOnlyElement(tomcatState.getInstancesIds());
		return tomcatInstanceId;
	}

	private ServiceOrchestratorState getTomcatServiceState() {
		return client.getExecutorState(orchestratorExecutorId, ServiceOrchestratorState.class);
	}
	
	
	@Test
	public void installServiceAndStartAgentTest() {
		
		installService();		
		orchestratorContainer.stepTaskExecutor();
		
		orchestrate();
		orchestratorContainer.stepTaskExecutor();
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
		//Initiate machine creation
		cloudContainer.stepTaskExecutor();
		//Finish machine started on localhost
		cloudExecutor.signalLastStartedMachineFinished("localhost");		
		orchestrate();
		
		//simulate implementation of StartAgentTask
		StartAgentTask lastAgentLifecycleTask = taskConsumer.getElement(taskConsumer.getLastElementId(agentLifecycleExecutorId), StartAgentTask.class);
		URL agentExecutorId = lastAgentLifecycleTask.getAgentExecutorId();
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
