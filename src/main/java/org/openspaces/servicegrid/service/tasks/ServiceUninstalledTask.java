package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceUninstalledTask extends ImpersonatingTask {

	public ServiceUninstalledTask() {
		super(ServiceState.class);
	}
}
