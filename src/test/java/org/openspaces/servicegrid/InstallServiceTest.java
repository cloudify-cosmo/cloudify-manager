package org.openspaces.servicegrid;

import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNull;
import static org.testng.Assert.assertTrue;
import static org.testng.Assert.fail;

import java.net.MalformedURLException;
import java.net.URL;

import org.openspaces.servicegrid.client.ServiceClient;
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
	
	//private URL agentLifecycleExecutorId;
	//private MockAgentLifecycleTaskExecutor agentExecutor;
	//private MockTaskContainer agentLifecycleContainer;
	
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
		orchestratorContainer = new MockTaskContainer(orchestratorExecutorId, stateWriter, taskConsumer, orchestrator);
		cloudContainer = new MockTaskContainer(cloudExecutorId, stateWriter, taskConsumer, cloudExecutor);
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
		
		final ServiceOrchestratorState serviceState = client.getExecutorState(orchestratorExecutorId);
		assertNull(serviceState.getDisplayName());
	}
	
	
	@Test
	public void installServiceStepExecutorTest() {
		
		installService();		
		assertNull(client.<ServiceOrchestratorState>getExecutorState(orchestratorExecutorId).getDisplayName());
		
		orchestratorContainer.stepTaskExecutor();
		final ServiceOrchestratorState serviceState = client.getExecutorState(orchestratorExecutorId);
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
		cloudContainer.stepTaskExecutor();
		assertTrue(getLastTask(cloudExecutorId) instanceof StartMachineTask);
		
		assertEquals(getTomcatInstanceState().getProgress(), ServiceInstanceState.Progress.STARTING_MACHINE);
	}

	private Task getLastTask(URL executorId) {
		final TaskExecutorState cloudExecutorState = client.getExecutorState(executorId);
		final URL taskId = cloudExecutorState.getLastCompletedTaskId();
		final Task lastCloudTask = client.getTask(taskId);
		return lastCloudTask;
	}

	private ServiceInstanceState getTomcatInstanceState() {
		final ServiceOrchestratorState tomcatState = client.getExecutorState(orchestratorExecutorId);
		final URL tomcatInstanceId = Iterables.getOnlyElement(tomcatState.getInstanceIds());
		final ServiceInstanceState tomcatInstanceState = client.getExecutorState(tomcatInstanceId);
		return tomcatInstanceState;
	}
	
	
	@Test
	public void installServiceAndStartAgentTest() {
		
		installService();		
		orchestratorContainer.stepTaskExecutor();
		
		orchestrate();
		orchestratorContainer.stepTaskExecutor();
		//Initiate machine creation
		cloudContainer.stepTaskExecutor();
		//Finish machine started on localhost
		cloudExecutor.signalLastStartedMachineFinished("localhost");		
		assertEquals(getTomcatInstanceState().getProgress(), ServiceInstanceState.Progress.MACHINE_STARTED);
		
		orchestrate();
		orchestratorContainer.stepTaskExecutor();
		
		StartAgentTask lastElement = (StartAgentTask) taskConsumer.getElement(taskConsumer.getLastElementId(agentLifecycleExecutorId));
		// make sure agent is installed on correct ip address
		assertEquals(lastElement.getIpAddress(), "localhost");
		
	}

	private void orchestrate() {
		client.addServiceTask(orchestratorExecutorId, new OrchestrateTask());
	}

}
