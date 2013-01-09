package org.openspaces.servicegrid.service.state;

import java.net.URI;

import org.openspaces.servicegrid.TaskExecutorState;

public class ServiceInstanceState extends TaskExecutorState {

	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String INSTALLING_INSTANCE = "INSTALLING_INSTANCE";
		public static final String INSTANCE_INSTALLED = "INSTANCE_INSTALLED";
		public static final String STARTING_INSTANCE = "STARTING_INSTANCE";
		public static final String INSTANCE_STARTED = "INSTANCE_STARTED";
	}
	
	private String progress;
	private URI agentId;
	private String displayName;
	
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

	public String getDisplayName() {
		return displayName;
	}
	
	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}
	
	

}
