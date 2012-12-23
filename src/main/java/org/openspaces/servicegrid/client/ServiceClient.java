package org.openspaces.servicegrid.client;

import java.net.URL;

import org.openspaces.servicegrid.model.service.ServiceTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;

public class ServiceClient {

	private final StreamConsumer<TaskExecutorState> stateReader;
	private final StreamProducer<Task> taskProducer;
	private final StreamConsumer<Task> taskConsumer;

	public ServiceClient(
			StreamConsumer<TaskExecutorState> stateReader, 
			StreamConsumer<Task> taskConsumer,
			StreamProducer<Task> taskProducer) {
		this.stateReader = stateReader;
		this.taskConsumer = taskConsumer;
		this.taskProducer = taskProducer;
	}
	
	public URL addServiceTask(URL serviceId, ServiceTask task) {
		Preconditions.checkNotNull(serviceId);
		Preconditions.checkNotNull(task);
		task.setTarget(serviceId);
		return taskProducer.addElement(serviceId, task);
	}
	
	@SuppressWarnings("unchecked")
	public <T extends TaskExecutorState> T getExecutorState(URL serviceId) {
		URL lastElementId = stateReader.getLastElementId(serviceId);
		return (T) stateReader.getElement(lastElementId);
	}

	public Task getTask(URL taskId) {
		return (Task) taskConsumer.getElement(taskId);
	}
}