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
	
	private ServiceClient cli;
	private final URL tomcatServiceId;
	private ServiceOrchestrator orchestrator; 
	private MockTaskContainer orchestratorContainer;
	
	private MockTaskContainer cloudContainer;
	private CloudMachineTaskExecutor cloudExecutor;
		
	private final URL tomcatDownloadUrl;
	private final URL cloudExecutorId;
	
	public InstallServiceTest() {
		try {
			tomcatServiceId = new URL("http://localhost/services/tomcat/");
			tomcatDownloadUrl = new URL("http://repository.cloudifysource.org/org/apache/tomcat/apache-tomcat-7.0.23/tomcat.zip");
			cloudExecutorId = new URL("http://localhost/services/cloud");
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
		orchestrator = new ServiceOrchestrator(tomcatServiceId, cloudExecutorId, taskConsumer, taskProducer);
		cloudExecutor = new CloudMachineTaskExecutor();
		
		cli = new ServiceClient(stateReader, stateWriter, taskConsumer, taskProducer);
		orchestratorContainer = new MockTaskContainer(tomcatServiceId, stateWriter, taskConsumer, orchestrator);
		cloudContainer = new MockTaskContainer(cloudExecutorId, stateWriter, taskConsumer, cloudExecutor);
	}
	
	@Test
	public void createServiceGetServiceStateTest() {
		
		cli.createService(tomcatServiceId);
		final ServiceOrchestratorState serviceState = (ServiceOrchestratorState) cli.getServiceState(tomcatServiceId);
		assertNull(serviceState.getDownloadUrl());
	}
	
	@Test
	public void createServiceAlreadyExistsTest() {
		
		cli.createService(tomcatServiceId);
		try {
			cli.createService(tomcatServiceId);
			fail("Expected conflict");
		}
		catch (IllegalArgumentException e) {
			
		}
	}
	
	@Test
	public void installServiceTest() {
		
		createServiceGetServiceStateTest();
		InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setDownloadUrl(tomcatDownloadUrl);
		URL taskId = cli.addServiceTask(tomcatServiceId, installServiceTask);
		assertTrue(cli.getTask(taskId) instanceof InstallServiceTask);
		final ServiceOrchestratorState serviceState = (ServiceOrchestratorState) cli.getServiceState(tomcatServiceId);
		assertNull(serviceState.getDownloadUrl());
	}
	
	@Test
	public void installServiceAlreadyInstalledTest() {
		
		installServiceStepExecutorTest();
		
		InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setDownloadUrl(tomcatDownloadUrl);
		cli.addServiceTask(tomcatServiceId, installServiceTask);
		try {
			orchestratorContainer.stepTaskExecutor();
			fail("Expected exception");
		}
		catch (IllegalStateException e) {
			
		}
	}

	@Test
	public void installServiceStepExecutorTest() {
		
		installServiceTest();
		orchestratorContainer.stepTaskExecutor();
		final ServiceOrchestratorState serviceState = (ServiceOrchestratorState) cli.getServiceState(tomcatServiceId);
		assertEquals(serviceState.getDownloadUrl(), tomcatDownloadUrl);
		URL taskId = serviceState.getLastCompletedTaskId();
		assertTrue(cli.getTask(taskId) instanceof InstallServiceTask);
	}

	@Test
	public void installServiceStepExecutorTwiceTest() {
		installServiceStepExecutorTest();
		orchestratorContainer.stepTaskExecutor();
	}
	
	@Test
	public void installServiceAndStartMachineTest() {
		
		installServiceStepExecutorTest();
		cli.addServiceTask(tomcatServiceId, new OrchestrateTask());
		orchestratorContainer.stepTaskExecutor();
		cloudContainer.stepTaskExecutor();
		final TaskExecutorState cloudState = cli.getServiceState(cloudExecutorId);
		URL taskId = cloudState.getLastCompletedTaskId();
		assertTrue(cli.getTask(taskId) instanceof StartMachineTask);
		
		final ServiceOrchestratorState tomcatState = (ServiceOrchestratorState) cli.getServiceState(tomcatServiceId);
		URL tomcatInstanceId = Iterables.getOnlyElement(tomcatState.getInstanceIds());
		ServiceInstanceState tomcatInstanceState = (ServiceInstanceState) cli.getServiceState(tomcatInstanceId);
		assertEquals(tomcatInstanceState.getProgress(), ServiceInstanceState.Progress.STARTING_MACHINE);
	}

}
