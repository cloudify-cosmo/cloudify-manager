package org.openspaces.servicegrid.client;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamWriter;

import com.google.common.base.Preconditions;

public class ServiceClient {

	private final StreamReader<TaskConsumerState> stateReader;
	private final StreamWriter<Task> taskProducer;
	private final StreamReader<Task> taskConsumer;

	public ServiceClient(
			ServiceClientParameter parameterObject) {
		this.stateReader = parameterObject.getStateReader();
		this.taskConsumer = parameterObject.getTaskReader();
		this.taskProducer = parameterObject.getTaskWriter();
	}
	
	public URI addServiceTask(URI serviceId, Task task) {
		Preconditions.checkNotNull(serviceId);
		Preconditions.checkNotNull(task);
		task.setTarget(serviceId);
		return taskProducer.addElement(serviceId, task);
	}
	
	public <T extends TaskConsumerState> T getExecutorState(URI serviceId, Class<T> clazz) {
		URI lastElementId = stateReader.getLastElementId(serviceId);
		return stateReader.getElement(lastElementId, clazz);
	}

	public Task getTask(URI taskId) {
		return taskConsumer.getElement(taskId, Task.class);
	}
}