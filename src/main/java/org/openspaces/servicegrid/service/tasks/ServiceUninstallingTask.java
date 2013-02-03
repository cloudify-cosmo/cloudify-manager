package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceState;

public class ServiceUninstallingTask extends ImpersonatingTask {

	public ServiceUninstallingTask() {
		super(ServiceState.class);
	}
}
