package org.openspaces.servicegrid.mock;

import java.net.URI;

import org.openspaces.servicegrid.TaskReader;
import org.openspaces.servicegrid.TaskWriter;
import org.openspaces.servicegrid.state.StateReader;
import org.openspaces.servicegrid.state.StateWriter;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class MockTaskContainerParameter {
	private URI executorId;
	private StateReader stateReader;
	private StateWriter stateWriter;
	private TaskReader taskReader;
	private TaskWriter taskWriter;
	private Object taskConsumer;
	private CurrentTimeProvider timeProvider;
	private TaskReader persistentTaskReader;
	private TaskWriter persistentTaskWriter;

	public MockTaskContainerParameter() {
	}

	public StateReader getStateReader() {
		return stateReader;
	}

	public void setStateReader(StateReader stateReader) {
		this.stateReader = stateReader;
	}

	public URI getExecutorId() {
		return executorId;
	}

	public void setExecutorId(URI executorId) {
		this.executorId = executorId;
	}

	public StateWriter getStateWriter() {
		return stateWriter;
	}

	public void setStateWriter(StateWriter stateWriter) {
		this.stateWriter = stateWriter;
	}

	public TaskWriter getTaskWriter() {
		return taskWriter;
	}

	public void setTaskWriter(TaskWriter taskWriter) {
		this.taskWriter = taskWriter;
	}

	public Object getTaskConsumer() {
		return taskConsumer;
	}

	public void setTaskConsumer(Object taskConsumer) {
		this.taskConsumer = taskConsumer;
	}

	public TaskReader getTaskReader() {
		return taskReader;
	}

	public void setTaskReader(TaskReader taskReader) {
		this.taskReader = taskReader;
	}

	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}

	public TaskReader getPersistentTaskReader() {
		return persistentTaskReader;
	}

	public void setPersistentTaskReader(TaskReader persistentTaskReader) {
		this.persistentTaskReader = persistentTaskReader;
	}

	public TaskWriter getPersistentTaskWriter() {
		return persistentTaskWriter;
	}

	public void setPersistentTaskWriter(TaskWriter persistentTaskWriter) {
		this.persistentTaskWriter = persistentTaskWriter;
	}
}