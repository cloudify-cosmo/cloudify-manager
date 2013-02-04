package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceInstallingTask extends Task {

	public ServiceInstallingTask() {
		super(ServiceState.class);
	}
}
