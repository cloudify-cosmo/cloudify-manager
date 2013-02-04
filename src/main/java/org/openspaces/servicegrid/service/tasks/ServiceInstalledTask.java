package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceInstalledTask extends Task {

	public ServiceInstalledTask() {
		super(ServiceState.class);
	}
}
