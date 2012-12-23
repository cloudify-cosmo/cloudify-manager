package org.openspaces.servicegrid;

import static org.testng.Assert.assertEquals;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.List;

import org.openspaces.servicegrid.client.ServiceClient;
import org.openspaces.servicegrid.model.service.InstallServiceTask;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
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

public class ServiceOrchestrationTest {
	
	private StreamConsumer<TaskExecutorState> stateReader;
	private ServiceClient client;
	private List<MockTaskContainer> containers;
	private URL orchestratorExecutorId;
	private MockTaskContainer orchestratorContainer;

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
		
		MockStreams<TaskExecutorState> state = new MockStreams<TaskExecutorState>();
		StreamProducer<TaskExecutorState> stateWriter = state;
		stateReader = state;
	
		MockStreams<Task> taskBroker = new MockStreams<Task>();
		StreamProducer<Task> taskProducer = taskBroker;
		StreamConsumer<Task> taskConsumer = taskBroker;
		
		stateWriter.addElement(orchestratorExecutorId, new ServiceOrchestratorState());
	
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
				stateWriter, 
				taskConsumer, 
				new ServiceOrchestrator(
						serviceOrchestratorParameter));

		containers = Lists.newArrayList(
								
				new MockTaskContainer(
						cloudExecutorId, 
						stateWriter,
						taskConsumer, 
						new MockCloudMachineTaskExecutor()));
	}
	
	@Test
	public void installSingleInstanceServiceTest() {
		installService();
		execute();
		final ServiceOrchestratorState serviceState = stateReader.getElement(stateReader.getLastElementId(orchestratorExecutorId));
		final URL serviceInstanceExecutorId = Iterables.getOnlyElement(serviceState.getInstanceIds());
		
		URL stateId0 = stateReader.getFirstElementId(serviceInstanceExecutorId);
		ServiceInstanceState state0 = stateReader.getElement(stateId0);
		assertEquals(state0.getProgress(), ServiceInstanceState.Progress.STARTING_MACHINE);
		assertEquals(state0.getDisplayName(), "tomcat");
		
		//URL state1 = stateReader.getNextElementId(state0);
		//URL state2 = stateReader.getNextElementId(state1);
		
	}
	
	private void installService() {
		final InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setDisplayName("tomcat");
		client.addServiceTask(orchestratorExecutorId, installServiceTask);
		orchestrate();
	}

	private void orchestrate() {
		client.addServiceTask(orchestratorExecutorId, new OrchestrateTask());
		orchestratorContainer.stepTaskExecutor();
	}
	
	private void execute() {
		boolean stop = true;
		for (int i = 0 ; i < 1000 ;i++) {

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
		
		Assert.fail("execute too many cycles");
	}
}
