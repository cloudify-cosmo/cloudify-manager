package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class InstallServiceInstanceTask extends Task {

	public InstallServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

}
