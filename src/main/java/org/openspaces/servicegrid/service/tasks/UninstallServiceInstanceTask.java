package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class UninstallServiceInstanceTask extends Task {

	public UninstallServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

}
