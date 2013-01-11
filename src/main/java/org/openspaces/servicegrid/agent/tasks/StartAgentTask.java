package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;

public class StartAgentTask extends ImpersonatingTask {

	private String ipAddress;

	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

}
