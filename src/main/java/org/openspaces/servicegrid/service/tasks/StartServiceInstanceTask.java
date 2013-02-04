package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;


public class StartServiceInstanceTask extends Task {

	public StartServiceInstanceTask() {
		super(ServiceInstanceState.class);
	}
}
