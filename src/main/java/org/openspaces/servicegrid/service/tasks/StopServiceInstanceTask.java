package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class StopServiceInstanceTask extends ImpersonatingTask {

	public StopServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

}
