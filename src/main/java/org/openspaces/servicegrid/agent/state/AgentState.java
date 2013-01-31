package org.openspaces.servicegrid.agent.state;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;

public class AgentState extends TaskConsumerState {
	
	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String STARTING_MACHINE = "STARTING_MACHINE"; 
		public static final String MACHINE_STARTED = "MACHINE_STARTED";
		public static final String AGENT_STARTED = "AGENT_STARTED";
		public static final String STOPPING_AGENT = "STOPPING_AGENT";
		public static final String TERMINATING_MACHINE = "TERMINATING_MACHINE";
		public static final String MACHINE_TERMINATED = "MACHINE_TERMINATED";
	}

	private String progress;
	private String ipAddress;
	private List<URI> serviceInstanceIds;
	private int numberOfAgentRestarts;
	private int numberOfMachineRestarts;
	private long lastPingSourceTimestamp;

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

	public int getNumberOfAgentRestarts() {
		return numberOfAgentRestarts;
	}

	public void setNumberOfAgentRestarts(int numberOfAgentRestarts) {
		this.numberOfAgentRestarts = numberOfAgentRestarts;
	}

	public int getNumberOfMachineRestarts() {
		return numberOfMachineRestarts;
	}

	public void setNumberOfMachineRestarts(int numberOfMachineRestarts) {
		this.numberOfMachineRestarts = numberOfMachineRestarts;
	}

	@JsonIgnore
	public void removeServiceInstanceId(final URI instanceId) {
		boolean removed = serviceInstanceIds.remove(instanceId);
		Preconditions.checkArgument(removed, "Cannot remove instance %s",instanceId);
	}

	public long getLastPingSourceTimestamp() {
		return lastPingSourceTimestamp;
	}

	public void setLastPingSourceTimestamp(long lastPingSourceTimestamp) {
		this.lastPingSourceTimestamp = lastPingSourceTimestamp;
	}
}
