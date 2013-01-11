package org.openspaces.servicegrid.client;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamWriter;

public class ServiceClientParameter {
	
	private StreamReader<TaskConsumerState> stateReader;
	private StreamReader<Task> taskReader;
	private StreamWriter<Task> taskWriter;

	public ServiceClientParameter() {
	}

	public StreamReader<TaskConsumerState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamReader<TaskConsumerState> stateReader) {
		this.stateReader = stateReader;
	}

	public StreamReader<Task> getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(StreamReader<Task> taskReader) {
		this.taskReader = taskReader;
	}

	public StreamWriter<Task> getTaskWriter() {
		return taskWriter;
	}

	public void setTaskWriter(StreamWriter<Task> taskProducer) {
		this.taskWriter = taskProducer;
	}
}