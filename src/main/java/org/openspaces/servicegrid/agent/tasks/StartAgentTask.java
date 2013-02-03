package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.agent.state.AgentState;

public class StartAgentTask extends ImpersonatingTask {

	public StartAgentTask() {
		super(AgentState.class);
	}
	
	private String ipAddress;

	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

}
