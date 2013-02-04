package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceUninstalledTask extends Task {

	public ServiceUninstalledTask() {
		super(ServiceState.class);
	}
}
