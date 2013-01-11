package org.openspaces.servicegrid.client;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.service.tasks.ServiceTask;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;

public class ServiceClient {

	private final StreamConsumer<TaskExecutorState> stateReader;
	private final StreamProducer<Task> taskProducer;
	private final StreamConsumer<Task> taskConsumer;

	public ServiceClient(
			ServiceClientParameter parameterObject) {
		this.stateReader = parameterObject.getStateReader();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.taskProducer = parameterObject.getTaskProducer();
	}
	
	public URI addServiceTask(URI serviceId, ServiceTask task) {
		Preconditions.checkNotNull(serviceId);
		Preconditions.checkNotNull(task);
		task.setTarget(serviceId);
		return taskProducer.addElement(serviceId, task);
	}
	
	public <T extends TaskExecutorState> T getExecutorState(URI serviceId, Class<T> clazz) {
		URI lastElementId = stateReader.getLastElementId(serviceId);
		return stateReader.getElement(lastElementId, clazz);
	}

	public Task getTask(URI taskId) {
		return taskConsumer.getElement(taskId, Task.class);
	}
}