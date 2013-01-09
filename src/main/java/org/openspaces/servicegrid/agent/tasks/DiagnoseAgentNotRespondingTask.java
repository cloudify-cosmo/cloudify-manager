package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;

public class DiagnoseAgentNotRespondingTask extends Task {

	private String ipAddress;
	
	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

}
