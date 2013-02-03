package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;


public class StartServiceInstanceTask extends ImpersonatingTask {

	public StartServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}
}
