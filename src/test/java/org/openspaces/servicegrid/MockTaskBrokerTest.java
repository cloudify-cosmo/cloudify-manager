package org.openspaces.servicegrid;

import java.net.URI;

import org.openspaces.servicegrid.mock.MockTaskBroker;
import org.openspaces.servicegrid.streams.StreamUtils;
import org.testng.Assert;
import org.testng.annotations.Test;

import com.google.common.collect.Iterables;

public class MockTaskBrokerTest {

	final URI taskConsumerId1 = StreamUtils.newURI("http://localhost/services/tomcat");
	final URI taskConsumerId2 = StreamUtils.newURI("http://localhost/services/cassandra");
	
	@Test
	public void getSingleTaskTest() {
		MockTaskBroker broker = new MockTaskBroker();
		final Task task = new Task(TaskConsumerState.class);
		task.setProducerTimestamp(1L);
		task.setConsumerId(taskConsumerId1);
		broker.postNewTask(task);
		
		Assert.assertTrue(broker.taskEquals(task,Iterables.getOnlyElement(broker.getPendingTasks(taskConsumerId1))));
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
		final Task firstTask = new Task(TaskConsumerState.class);
		firstTask.setProducerTimestamp(1L);
		firstTask.setConsumerId(taskConsumerId1);
		broker.postNewTask(firstTask);
		
		final Task secondTask = new Task(TaskConsumerState.class);
		secondTask.setProducerTimestamp(2L);
		secondTask.setConsumerId(taskConsumerId1);
		broker.postNewTask(secondTask);
		Assert.assertEquals(Iterables.size(broker.getPendingTasks(taskConsumerId1)), 2);
		Assert.assertTrue(broker.taskEquals(firstTask,broker.removeNextTask(taskConsumerId1)));
		Assert.assertTrue(broker.taskEquals(secondTask, broker.removeNextTask(taskConsumerId1)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
	}
	
	public void getSingleTaskTwoConsumersTest() {
		MockTaskBroker broker = new MockTaskBroker();
		final Task task1 = new Task(TaskConsumerState.class);
		task1.setProducerTimestamp(1L);
		task1.setConsumerId(taskConsumerId1);
		broker.postNewTask(task1);
		
		final Task task2 = new Task(TaskConsumerState.class);
		task2.setProducerTimestamp(2L);
		task2.setConsumerId(taskConsumerId2);
		broker.postNewTask(task2);
		
		Assert.assertTrue(broker.taskEquals(task1,broker.removeNextTask(taskConsumerId1)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId1));
		Assert.assertTrue(broker.taskEquals(task2,broker.removeNextTask(taskConsumerId2)));
		Assert.assertEquals(null, broker.removeNextTask(taskConsumerId2));
	}
}
