package org.openspaces.servicegrid;

import java.net.URI;

import org.openspaces.servicegrid.mock.MockTaskBroker;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.testng.Assert;
import org.testng.annotations.Test;

import com.google.common.collect.Iterables;

public class MockTaskBrokerTest {

	final URI taskConsumerId1 = StreamUtils.newURI("http://localhost/services/tomcat");
	final URI taskConsumerId2 = StreamUtils.newURI("http://localhost/services/cassandra");
	final URI taskProducerId = StreamUtils.newURI("http://localhost/test");
	@Test
	public void getSingleTaskTest() {
		MockTaskBroker broker = new MockTaskBroker();
		final InstallServiceTask task = new InstallServiceTask();
		task.setProducerTimestamp(1L);
		task.setConsumerId(taskConsumerId1);
		task.setProducerId(taskProducerId);
		task.setStateId(taskConsumerId1);
		task.setServiceConfig(new ServiceConfig());
		broker.postNewTask(task);
		
		Task pendingTask = Iterables.getOnlyElement(broker.getPendingTasks(taskConsumerId1));
		Assert.assertTrue(broker.taskEquals(task,pendingTask));
		Assert.assertTrue(broker.taskEquals(task,broker.removeNextTask(taskConsumerId1)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
	}
	
	@Test
	public void getNoTaskTest() {
		
		MockTaskBroker broker = new MockTaskBroker();
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
		Assert.assertTrue(Iterables.isEmpty(broker.getPendingTasks(taskConsumerId1)));
	}
	
	@Test
	public void getTaskFifoTest() {
		MockTaskBroker broker = new MockTaskBroker();
		final InstallServiceTask firstTask = new InstallServiceTask();
		firstTask.setProducerTimestamp(1L);
		firstTask.setConsumerId(taskConsumerId1);
		firstTask.setProducerId(taskProducerId);
		firstTask.setStateId(taskConsumerId1);
		firstTask.setServiceConfig(new ServiceConfig());
		broker.postNewTask(firstTask);
		
		final InstallServiceTask secondTask = new InstallServiceTask();
		secondTask.setProducerTimestamp(2L);
		secondTask.setConsumerId(taskConsumerId1);
		secondTask.setProducerId(taskProducerId);
		secondTask.setStateId(taskConsumerId1);
		ServiceConfig serviceConfig2 = new ServiceConfig();
		serviceConfig2.setPlannedNumberOfInstances(2);
		secondTask.setServiceConfig(serviceConfig2);
		
		broker.postNewTask(secondTask);
		Assert.assertEquals(Iterables.size(broker.getPendingTasks(taskConsumerId1)), 2);
		Assert.assertTrue(broker.taskEquals(firstTask,broker.removeNextTask(taskConsumerId1)));
		Assert.assertTrue(broker.taskEquals(secondTask, broker.removeNextTask(taskConsumerId1)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
	}
	
	@Test
	public void submitSameTaskTwiceTest() {
		MockTaskBroker broker = new MockTaskBroker();
		final InstallServiceTask firstTask = new InstallServiceTask();
		firstTask.setProducerTimestamp(1L);
		firstTask.setConsumerId(taskConsumerId1);
		firstTask.setProducerId(taskProducerId);
		firstTask.setStateId(taskConsumerId1);
		firstTask.setServiceConfig(new ServiceConfig());
		firstTask.setProducerTimestamp(0L);
		broker.postNewTask(firstTask);
		
		final InstallServiceTask secondTask = new InstallServiceTask();
		secondTask.setProducerTimestamp(2L);
		secondTask.setConsumerId(taskConsumerId1);
		secondTask.setProducerId(taskProducerId);
		secondTask.setStateId(taskConsumerId1);
		secondTask.setServiceConfig(new ServiceConfig());
		secondTask.setProducerTimestamp(1L);
		
		broker.postNewTask(secondTask);
		Assert.assertEquals(Iterables.size(broker.getPendingTasks(taskConsumerId1)), 1);
		Assert.assertTrue(broker.taskEquals(firstTask,broker.removeNextTask(taskConsumerId1)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
	}
	
	public void getSingleTaskTwoConsumersTest() {
		MockTaskBroker broker = new MockTaskBroker();
		final Task task1 = new InstallServiceTask();
		task1.setProducerTimestamp(1L);
		task1.setConsumerId(taskConsumerId1);
		broker.postNewTask(task1);
		
		final Task task2 = new InstallServiceTask();
		task2.setProducerTimestamp(2L);
		task2.setConsumerId(taskConsumerId2);
		broker.postNewTask(task2);
		
		Assert.assertTrue(broker.taskEquals(task1,broker.removeNextTask(taskConsumerId1)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
		Assert.assertTrue(broker.taskEquals(task2,broker.removeNextTask(taskConsumerId2)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId2));
	}
}
