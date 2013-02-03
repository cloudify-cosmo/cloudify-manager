package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceInstalledTask extends ImpersonatingTask {

	public ServiceInstalledTask() {
		super(ServiceState.class);
	}
}
