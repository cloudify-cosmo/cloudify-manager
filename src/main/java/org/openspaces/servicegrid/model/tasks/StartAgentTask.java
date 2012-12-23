package org.openspaces.servicegrid.model.tasks;

import org.openspaces.servicegrid.model.tasks.Task;

public class StartAgentTask extends Task {

	private String ipAddress;

	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

}
