package org.openspaces.servicegrid.model.tasks;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.Task;

public class StartAgentTask extends Task {

	private String ipAddress;
	private URL agentExecutorId;

	public URL getAgentExecutorId() {
		return agentExecutorId;
	}

	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

	public void setAgentExecutorId(URL agentExecutorId) {
		this.agentExecutorId = agentExecutorId;
	}

}
