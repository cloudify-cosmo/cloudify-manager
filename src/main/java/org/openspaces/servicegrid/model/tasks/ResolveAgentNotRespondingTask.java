package org.openspaces.servicegrid.model.tasks;

import java.net.URI;

import org.openspaces.servicegrid.model.tasks.Task;

public class ResolveAgentNotRespondingTask extends Task {

	private String ipAddress;
	private URI zombieAgentExecutorId;
	
	public String getIpAddress() {
		return ipAddress;
	}

	public void setIpAddress(String ipAddress) {
		this.ipAddress = ipAddress;
	}

	public URI getZombieAgentExecutorId() {
		return zombieAgentExecutorId;
	}

	public void setZombieAgentExecutorId(URI zombieAgentExecutorId) {
		this.zombieAgentExecutorId = zombieAgentExecutorId;
	}

}
