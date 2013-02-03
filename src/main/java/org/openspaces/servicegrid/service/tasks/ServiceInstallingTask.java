package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceInstallingTask extends ImpersonatingTask {

	public ServiceInstallingTask() {
		super(ServiceState.class);
	}
}
