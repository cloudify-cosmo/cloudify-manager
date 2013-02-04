package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class StopServiceInstanceTask extends Task {

	public StopServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}

}
