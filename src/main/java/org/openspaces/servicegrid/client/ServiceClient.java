package org.openspaces.servicegrid.client;

import java.net.URL;

import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.service.ServiceTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;

public class ServiceClient {

	private final StreamProducer<TaskExecutorState> stateWriter;
	private final StreamConsumer<TaskExecutorState> stateReader;
	private final StreamProducer<Task> taskProducer;
	private final StreamConsumer<Task> taskConsumer;

	public ServiceClient(
			StreamConsumer<TaskExecutorState> stateReader, 
			StreamProducer<TaskExecutorState> stateWriter,
			StreamConsumer<Task> taskConsumer,
			StreamProducer<Task> taskProducer) {
		this.stateReader = stateReader;
		this.stateWriter = stateWriter;
		this.taskConsumer = taskConsumer;
		this.taskProducer = taskProducer;
	}

	public void createService(URL serviceId) {
		final ServiceOrchestratorState orchestratorState = new ServiceOrchestratorState();
		stateWriter.addFirstElement(serviceId, orchestratorState);
	}
	
	public URL addServiceTask(URL serviceId, ServiceTask task) {
		Preconditions.checkNotNull(serviceId);
		Preconditions.checkNotNull(task);
		task.setTarget(serviceId);
		return taskProducer.addElement(serviceId, task);
	}
	
	public <T extends TaskExecutorState> T getServiceState(URL serviceId) {
		return (T) stateReader.getElement(stateReader.getLastElementId(serviceId));
	}

	public Task getTask(URL taskId) {
		return (Task) taskConsumer.getElement(taskId);
	}
}