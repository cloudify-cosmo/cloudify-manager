package org.openspaces.servicegrid.model.service;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class ServiceInstanceState extends TaskExecutorState {

	public static class Progress{
		public static final String STARTING_MACHINE = "STARTING_MACHINE"; 
		public static final String MACHINE_STARTED = "MACHINE_STARTED";
		public static final String AGENT_STARTED = "AGENT_STARTED";
	}
	
	private String progress;
	private String ipAddress;
	private URL agentExecutorId;
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

	public URL getAgentExecutorId() {
		return agentExecutorId;
	}

	public void setAgentExecutorId(URL agentExecutorId) {
		this.agentExecutorId = agentExecutorId;
	}

	public String getDisplayName() {
		return displayName;
	}
	
	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}
	
	

}
