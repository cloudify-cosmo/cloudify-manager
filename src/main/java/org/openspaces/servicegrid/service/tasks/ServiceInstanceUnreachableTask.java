package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class ServiceInstanceUnreachableTask extends Task{

	public ServiceInstanceUnreachableTask() {
		super(ServiceInstanceState.class);
	}
}
