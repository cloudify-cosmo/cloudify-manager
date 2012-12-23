package org.openspaces.servicegrid.model.service;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class ServiceInstanceState extends TaskExecutorState {

	public static class Progress{
		public static final String STARTING_MACHINE = "STARTING_MACHINE"; 
		public static final String MACHINE_STARTED = "MACHINE_STARTED";
	}
	
	private String progress;
	private String ipAddress;
	
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
	
	

}
