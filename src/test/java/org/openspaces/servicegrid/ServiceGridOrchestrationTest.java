package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
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
import org.testng.Assert;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Sets;

public class ServiceGridOrchestrationTest {
	
	private ServiceClient client;
	private Set<MockTaskContainer> containers;
	private URL orchestratorExecutorId;
	private MockTaskContainer orchestratorContainer;
	private MockStreams<TaskExecutorState> state;
	private StreamConsumer<Task> taskConsumer;
	private final Logger logger = Logger.getLogger(this.getClass().getName());

	@BeforeMethod
	public void before() {
		
		final URL cloudExecutorId;
		final URL agentLifecycleExecutorId;
		
		try {
			orchestratorExecutorId = new URL("http://localhost/services/tomcat/");
			cloudExecutorId = new URL("http://localhost/services/cloud");
			agentLifecycleExecutorId = new URL("http://localhost/services/agentLifecycle");
		} catch (MalformedURLException e) {
			throw Throwables.propagate(e);
		}
		
		state = new MockStreams<TaskExecutorState>();
		StreamProducer<TaskExecutorState> stateWriter = state;
		StreamConsumer<TaskExecutorState> stateReader = state;
	
		MockStreams<Task> taskBroker = new MockStreams<Task>();
		StreamProducer<Task> taskProducer = taskBroker;
		taskConsumer = taskBroker;
		
		stateWriter.addElement(orchestratorExecutorId, new ServiceGridOrchestratorState());
	
		client = new ServiceClient(stateReader, taskConsumer, taskProducer);
	
		final ServiceOrchestratorParameter serviceOrchestratorParameter = new ServiceOrchestratorParameter();
		serviceOrchestratorParameter.setOrchestratorExecutorId(orchestratorExecutorId);
		serviceOrchestratorParameter.setCloudExecutorId(cloudExecutorId);
		serviceOrchestratorParameter.setAgentLifecycleExecutorId(agentLifecycleExecutorId);
		serviceOrchestratorParameter.setTaskConsumer(taskConsumer);
		serviceOrchestratorParameter.setTaskProducer(taskProducer);
		serviceOrchestratorParameter.setStateReader(stateReader);
	
		orchestratorContainer = new MockTaskContainer(
				orchestratorExecutorId,
				stateReader, stateWriter, 
				taskConsumer, 
				new ServiceGridOrchestrator(
						serviceOrchestratorParameter));

		containers = Sets.newCopyOnWriteArraySet(Lists.newArrayList(
				orchestratorContainer,				
				new MockTaskContainer(
						cloudExecutorId, 
						stateReader, stateWriter,
						taskConsumer, 
						new MockImmediateMachineSpawnerTaskExecutor()),
						
				new MockTaskContainer(
						agentLifecycleExecutorId, 
						stateReader, stateWriter,
						taskConsumer, 
						new MockEmbeddedAgentLifecycleTaskExecutor(new TaskExecutorWrapper() {
							
							@Override
							public void wrapTaskExecutor(
									TaskExecutor<? extends TaskExecutorState> taskExecutor, URL executorId) {
								containers.add(new MockTaskContainer(executorId, state, state, taskConsumer, taskExecutor));
							}
							
							@Override
							public void wrapImpersonatingTaskExecutor(
									ImpersonatingTaskExecutor<? extends TaskExecutorState> impersonatingTaskExecutor, URL executorId) {
								containers.add(new MockTaskContainer(executorId, state, state, taskConsumer, impersonatingTaskExecutor));								
							}
						}
						))
				));
	}
	
	@Test
	public void installSingleInstanceServiceTest() throws MalformedURLException {
		installService("tomcat", 1);
		execute();
		
		final ServiceState serviceState = state.getElement(state.getLastElementId(getServiceUrl("tomcat")), ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstancesIds()),1);
		logger.info("URLs: " + state.getElementIdsStartingWith(new URL("http://localhost/")));
		Iterable<URL> instanceIds = state.getElementIdsStartingWith(new URL("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),1);
		
		ServiceInstanceState instanceState = state.getElement(state.getLastElementId(Iterables.getOnlyElement(instanceIds)), ServiceInstanceState.class);
		Assert.assertEquals(instanceState.getDisplayName(), "tomcat");
		Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
		
		Iterable<URL> agentIds = state.getElementIdsStartingWith(new URL("http://localhost/agent/"));
		Assert.assertEquals(instanceState.getAgentExecutorId(),Iterables.getOnlyElement(agentIds));
	}
	
	@Test
	public void installMultipleInstanceServiceTest() throws MalformedURLException {
		installService("tomcat", 2);
		execute();
		
		final ServiceState serviceState = state.getElement(state.getLastElementId(getServiceUrl("tomcat")), ServiceState.class);
		Assert.assertEquals(Iterables.size(serviceState.getInstancesIds()),2);
		logger.info("URLs: " + state.getElementIdsStartingWith(new URL("http://localhost/")));
		Iterable<URL> instanceIds = state.getElementIdsStartingWith(new URL("http://localhost/services/tomcat/instances/"));
		Assert.assertEquals(Iterables.size(instanceIds),2);
		
		Iterable<URL> agentIds = state.getElementIdsStartingWith(new URL("http://localhost/agent/"));
		Assert.assertEquals(Iterables.size(agentIds), 2);
		for (URL url : instanceIds) {
			ServiceInstanceState instanceState = state.getElement(state.getLastElementId(url), ServiceInstanceState.class);
			Assert.assertEquals(instanceState.getDisplayName(), "tomcat");
			Assert.assertEquals(instanceState.getProgress(), ServiceInstanceState.Progress.INSTANCE_STARTED);
			Assert.assertTrue(Iterables.contains(agentIds, instanceState.getAgentExecutorId()));
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


	private void installService(String name, int numberOfInstances) throws MalformedURLException {
		ServiceConfig serviceConfig = new ServiceConfig();
		serviceConfig.setDisplayName(name);
		serviceConfig.setNumberOfInstances(numberOfInstances);
		serviceConfig.setServiceUrl(getServiceUrl(name));
		final InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setServiceConfig(serviceConfig);
		client.addServiceTask(orchestratorExecutorId, installServiceTask);
	}

	private URL getServiceUrl(String name) throws MalformedURLException {
		return new URL("http://services/" + name);
	}
	
	private void orchestrate() {
		client.addServiceTask(orchestratorExecutorId, new OrchestrateTask());
		orchestratorContainer.stepTaskExecutor();
	}
	
	private void execute() throws MalformedURLException {

		for (int i = 0 ; i < 1000 ;i++) {

			boolean stop = true;
			orchestrate();
			
			for (MockTaskContainer container : containers) {
				if (container.stepTaskExecutor()) {
					stop = false;
				}
			}

			if (stop) {
				return;
			}
		}
		StringBuilder sb = new StringBuilder();
		Iterable<URL> servicesIds = state.getElementIdsStartingWith(new URL("http://services/"));
		for (URL url : servicesIds) {
			ServiceState serviceState = state.getElement(state.getLastElementId(url), ServiceState.class);
			sb.append("service: " + serviceState.getServiceConfig().getDisplayName());
			sb.append(" - ");
			for (URL instanceUrl : serviceState.getInstancesIds()) {
				ServiceInstanceState instanceState = state.getElement(state.getLastElementId(instanceUrl), ServiceInstanceState.class);
				sb.append(instanceUrl).append("[").append(instanceState.getProgress()).append("] ");
			}
			
		}
		
		Assert.fail("Executing too many cycles progress=" + sb);
	}
}
