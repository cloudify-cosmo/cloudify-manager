package org.openspaces.servicegrid.agent.state;

import org.openspaces.servicegrid.TaskExecutorState;

public class AgentState extends TaskExecutorState {
	
	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String STARTING_MACHINE = "STARTING_MACHINE"; 
		public static final String MACHINE_STARTED = "MACHINE_STARTED";
		public static final String AGENT_STARTED = "AGENT_STARTED";
		public static final String AGENT_NOT_RESPONDING = "AGENT_NOT_RESPONDING";
	}

	private String progress;
	private String ipAddress;

	public String getProgress() {
		return progress;
	}

	public void setProgress(String progress) {
		this.progress = progress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}
	
	public String getIpAddress() {
		return ipAddress;
	}
}
