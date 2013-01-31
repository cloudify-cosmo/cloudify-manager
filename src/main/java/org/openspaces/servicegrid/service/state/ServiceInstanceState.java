package org.openspaces.servicegrid.service.state;

import java.net.URI;

import org.openspaces.servicegrid.TaskConsumerState;

public class ServiceInstanceState extends TaskConsumerState {

	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String INSTALLING_INSTANCE = "INSTALLING_INSTANCE";
		public static final String INSTANCE_INSTALLED = "INSTANCE_INSTALLED";
		public static final String STARTING_INSTANCE = "STARTING_INSTANCE";
		public static final String INSTANCE_STARTED = "INSTANCE_STARTED";
		public static final String STOPPING_INSTANCE = "STOPPING_INSTANCE";
		public static final String INSTANCE_STOPPED = "INSTANCE_STOPPED";
		public static final String INSTANCE_UNREACHABLE = "INSTANCE_UNREACHABLE";
	}
	
	private String progress;
	private URI agentId;
	private URI serviceId;
	
	public String getProgress() {
		return progress;
	}
	
	public void setProgress(String progress) {
		this.progress = progress;
	}

	public URI getAgentId() {
		return agentId;
	}

	public void setAgentId(URI agentId) {
		this.agentId = agentId;
	}

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
