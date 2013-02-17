package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class ServiceInstanceTask extends Task {

	private String lifecycle;
	
	public ServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

	public String getLifecycle() {
		return lifecycle;
	}

	public void setLifecycle(String lifecycle) {
		this.lifecycle = lifecycle;
	}
	
	

}
