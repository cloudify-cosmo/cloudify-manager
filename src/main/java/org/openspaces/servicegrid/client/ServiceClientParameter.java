package org.openspaces.servicegrid.client;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

public class ServiceClientParameter {
	
	private StreamConsumer<TaskExecutorState> stateReader;
	private StreamConsumer<Task> taskConsumer;
	private StreamProducer<Task> taskProducer;

	public ServiceClientParameter() {
	}

	public StreamConsumer<TaskExecutorState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamConsumer<TaskExecutorState> stateReader) {
		this.stateReader = stateReader;
	}

	public StreamConsumer<Task> getTaskConsumer() {
		return taskConsumer;
	}

	public void setTaskConsumer(StreamConsumer<Task> taskConsumer) {
		this.taskConsumer = taskConsumer;
	}

	public StreamProducer<Task> getTaskProducer() {
		return taskProducer;
	}

	public void setTaskProducer(StreamProducer<Task> taskProducer) {
		this.taskProducer = taskProducer;
	}
}