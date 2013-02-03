package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;


public class InstallServiceInstanceTask extends ImpersonatingTask {

	public InstallServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

}
