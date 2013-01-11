package org.openspaces.servicegrid.agent.state;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.TaskConsumerState;

public class AgentState extends TaskConsumerState {
	
	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String STARTING_MACHINE = "STARTING_MACHINE"; 
		public static final String MACHINE_STARTED = "MACHINE_STARTED";
		public static final String AGENT_STARTED = "AGENT_STARTED";
	}

	private String progress;
	private String ipAddress;
	private List<URI> serviceInstanceIds;
	private int numberOfRestarts;

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

	public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
		this.serviceInstanceIds = serviceInstanceIds;	
	}
	
	public List<URI> getServiceInstanceIds() {
		return serviceInstanceIds;
	}

	public int getNumberOfRestarts() {
		return numberOfRestarts;
	}

	public void setNumberOfRestarts(int numberOfRestarts) {
		this.numberOfRestarts = numberOfRestarts;
	}
}
