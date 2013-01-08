package org.openspaces.servicegrid;

import java.net.URI;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class ServiceOrchestratorParameter {
	
	private URI orchestratorExecutorId;
	private URI cloudExecutorId;
	private URI agentLifecycleExecutorId;
	private StreamConsumer<Task> taskConsumer;
	private StreamProducer<Task> taskProducer;
	private StreamConsumer<TaskExecutorState> stateReader;
	private CurrentTimeProvider timeProvider;
	
	public URI getAgentLifecycleExecutorId() {
		return agentLifecycleExecutorId;
	}

	public void setAgentLifecycleExecutorId(URI agentLifecycleExecutorId) {
		this.agentLifecycleExecutorId = agentLifecycleExecutorId;
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

	public StreamConsumer<TaskExecutorState> getStateReader() {
		return stateReader;
	}

	public void setStateReader(StreamConsumer<TaskExecutorState> stateReader) {
		this.stateReader = stateReader;
	}

	public URI getOrchestratorExecutorId() {
		return orchestratorExecutorId;
	}

	public void setOrchestratorExecutorId(URI orchestratorExecutorId) {
		this.orchestratorExecutorId = orchestratorExecutorId;
	}

	public URI getCloudExecutorId() {
		return cloudExecutorId;
	}

	public void setCloudExecutorId(URI cloudExecutorId) {
		this.cloudExecutorId = cloudExecutorId;
	}

	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}
}