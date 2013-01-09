package org.openspaces.servicegrid.service.state;

import java.net.URI;

import org.openspaces.servicegrid.TaskExecutorState;

public class ServiceInstanceState extends TaskExecutorState {

	public static class Progress{
		public static final String ORCHESTRATING = "ORCHESTRATING";
		public static final String STARTING_MACHINE = "STARTING_MACHINE"; 
		public static final String MACHINE_STARTED = "MACHINE_STARTED";
		public static final String AGENT_STARTED = "AGENT_STARTED";
		public static final String INSTALLING_INSTANCE = "INSTALLING_INSTANCE";
		public static final String INSTANCE_INSTALLED = "INSTANCE_INSTALLED";
		public static final String STARTING_INSTANCE = "STARTING_INSTANCE";
		public static final String INSTANCE_STARTED = "INSTANCE_STARTED";
		public static final String AGENT_NOT_RESPONDING = "AGENT_ZOMBIE";
	}
	
	private String progress;
	private String ipAddress;
	private URI agentExecutorId;
	private String displayName;
	
	public String getProgress() {
		return progress;
	}

	public void setProgress(String progress) {
		this.progress = progress;
	}

	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

	public URI getAgentExecutorId() {
		return agentExecutorId;
	}

	public void setAgentExecutorId(URI agentExecutorId) {
		this.agentExecutorId = agentExecutorId;
	}

	public String getDisplayName() {
		return displayName;
	}
	
	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}
	
	

}
