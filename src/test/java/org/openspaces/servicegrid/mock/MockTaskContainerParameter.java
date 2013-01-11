package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.MockCurrentTimeProvider;

public class MockTaskContainerParameter {
	private URI executorId;
	private StreamConsumer<TaskExecutorState> stateReader;
	private StreamProducer<TaskExecutorState> stateWriter;
	private StreamConsumer<Task> taskConsumer;
	private Object taskExecutor;
	private MockCurrentTimeProvider timeProvider;

	public MockTaskContainerParameter() {
	}

	public StreamConsumer<TaskExecutorState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamConsumer<TaskExecutorState> stateReader) {
		this.stateReader = stateReader;
	}

	public URI getExecutorId() {
		return executorId;
	}

	public void setExecutorId(URI executorId) {
		this.executorId = executorId;
	}

	public StreamProducer<TaskExecutorState> getStateWriter() {
		return stateWriter;
	}

	public void setStateWriter(StreamProducer<TaskExecutorState> stateWriter) {
		this.stateWriter = stateWriter;
	}

	public StreamConsumer<Task> getTaskConsumer() {
		return taskConsumer;
	}

	public void setTaskConsumer(StreamConsumer<Task> taskConsumer) {
		this.taskConsumer = taskConsumer;
	}

	public Object getTaskExecutor() {
		return taskExecutor;
	}

	public void setTaskExecutor(Object taskExecutor) {
		this.taskExecutor = taskExecutor;
	}

	public MockCurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(MockCurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}
}