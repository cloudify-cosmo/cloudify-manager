package org.openspaces.servicegrid.model.service;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public class ServiceInstanceState extends TaskExecutorState {

	public enum Progress {
		STARTING_MACHINE
	}
	
	private Progress progress;
	
	public Progress getProgress() {
		return progress;
	}

	public void setProgress(Progress progress) {
		this.progress = progress;
	}
	
	

}
