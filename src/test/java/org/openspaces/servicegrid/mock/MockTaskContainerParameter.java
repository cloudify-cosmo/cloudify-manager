package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.streams.StreamWriter;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class MockTaskContainerParameter {
	private URI executorId;
	private StreamReader<TaskConsumerState> stateReader;
	private StreamWriter<TaskConsumerState> stateWriter;
	private StreamReader<Task> taskReader;
	private StreamWriter<Task> taskWriter;
	private Object taskConsumer;
	private CurrentTimeProvider timeProvider;
	private StreamReader<Task> persistentTaskReader;
	private StreamWriter<Task> persistentTaskWriter;

	public MockTaskContainerParameter() {
	}

	public StreamReader<TaskConsumerState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamReader<TaskConsumerState> stateReader) {
		this.stateReader = stateReader;
	}

	public URI getExecutorId() {
		return executorId;
	}

	public void setExecutorId(URI executorId) {
		this.executorId = executorId;
	}

	public StreamWriter<TaskConsumerState> getStateWriter() {
		return stateWriter;
	}

	public void setStateWriter(StreamWriter<TaskConsumerState> stateWriter) {
		this.stateWriter = stateWriter;
	}

	public StreamWriter<Task> getTaskWriter() {
		return taskWriter;
	}

	public void setTaskWriter(StreamWriter<Task> taskWriter) {
		this.taskWriter = taskWriter;
	}

	public Object getTaskConsumer() {
		return taskConsumer;
	}

	public void setTaskConsumer(Object taskConsumer) {
		this.taskConsumer = taskConsumer;
	}

	public StreamReader<Task> getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(StreamReader<Task> taskReader) {
		this.taskReader = taskReader;
	}

	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}

	public StreamReader<Task> getPersistentTaskReader() {
		return persistentTaskReader;
	}

	public void setPersistentTaskReader(StreamReader<Task> persistentTaskReader) {
		this.persistentTaskReader = persistentTaskReader;
	}

	public StreamWriter<Task> getPersistentTaskWriter() {
		return persistentTaskWriter;
	}

	public void setPersistentTaskWriter(StreamWriter<Task> persistentTaskWriter) {
		this.persistentTaskWriter = persistentTaskWriter;
	}
}