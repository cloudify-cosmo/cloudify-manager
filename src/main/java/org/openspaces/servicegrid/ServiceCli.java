package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.tasks.ServiceTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.rest.HttpEtag;

import com.google.common.base.Preconditions;

public class ServiceCli {

	private final TaskExecutorStateWriter stateWriter;
	private final TaskExecutorStatePollingReader stateReader;
	private final TaskProducer taskProducer;
	private final TaskConsumer taskConsumer;

	public ServiceCli(
			TaskExecutorStatePollingReader stateReader, 
			TaskExecutorStateWriter stateWriter,
			TaskConsumer taskConsumer,
			TaskProducer taskProducer) {
		this.stateReader = stateReader;
		this.stateWriter = stateWriter;
		this.taskConsumer = taskConsumer;
		this.taskProducer = taskProducer;
	}

	public void createService(URL serviceId) {
		final ServiceOrchestratorState orchestratorState = new ServiceOrchestratorState();
		stateWriter.put(serviceId, orchestratorState, HttpEtag.NOT_EXISTS);
	}
	
	public URL addServiceTask(URL serviceId, ServiceTask task) {
		Preconditions.checkNotNull(serviceId);
		Preconditions.checkNotNull(task);
		task.setTarget(serviceId);
		return taskProducer.post(serviceId, task);
	}
	
	public TaskExecutorState getServiceState(URL serviceId) {
		return stateReader.get(serviceId);
	}

	public Task getTask(URL taskId) {
		return (Task) taskConsumer.get(taskId);
	}
}