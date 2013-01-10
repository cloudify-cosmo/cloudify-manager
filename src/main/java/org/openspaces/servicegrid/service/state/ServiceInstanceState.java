package org.openspaces.servicegrid.service.state;

import org.openspaces.servicegrid.TaskExecutorState;

public class ServiceInstanceState extends TaskExecutorState {

	public static class Progress{
		public static final String PLANNED = "PLANNED";
		public static final String INSTALLING_INSTANCE = "INSTALLING_INSTANCE";
		public static final String INSTANCE_INSTALLED = "INSTANCE_INSTALLED";
		public static final String STARTING_INSTANCE = "STARTING_INSTANCE";
		public static final String INSTANCE_STARTED = "INSTANCE_STARTED";
	}
	
	private String progress;
	private String displayName;
	
	public String getProgress() {
		return progress;
	}

	public void setProgress(String progress) {
		this.progress = progress;
	}

	public String getDisplayName() {
		return displayName;
	}
	
	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}
	
	

}
