package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class ServiceOrchestratorParameter {
	
	private URL orchestratorExecutorId;
	private URL cloudExecutorId;
	private URL agentLifecycleExecutorId;
	private StreamConsumer<Task> taskConsumer;
	private StreamProducer<Task> taskProducer;
	private StreamConsumer<TaskExecutorState> stateReader;
	private CurrentTimeProvider timeProvider;
	
	public URL getAgentLifecycleExecutorId() {
		return agentLifecycleExecutorId;
	}

	public void setAgentLifecycleExecutorId(URL agentLifecycleExecutorId) {
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

	public URL getOrchestratorExecutorId() {
		return orchestratorExecutorId;
	}

	public void setOrchestratorExecutorId(URL orchestratorExecutorId) {
		this.orchestratorExecutorId = orchestratorExecutorId;
	}

	public URL getCloudExecutorId() {
		return cloudExecutorId;
	}

	public void setCloudExecutorId(URL cloudExecutorId) {
		this.cloudExecutorId = cloudExecutorId;
	}

	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}
}