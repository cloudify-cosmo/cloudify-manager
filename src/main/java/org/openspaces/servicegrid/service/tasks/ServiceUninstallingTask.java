package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceState;


public class ServiceUninstallingTask extends Task {

	public ServiceUninstallingTask() {
		super(ServiceState.class);
	}
}
