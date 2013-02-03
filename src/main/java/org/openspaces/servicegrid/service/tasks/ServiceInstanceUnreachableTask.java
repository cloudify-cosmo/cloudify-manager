package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;

public class ServiceInstanceUnreachableTask extends ImpersonatingTask{

	public ServiceInstanceUnreachableTask() {
		super(ServiceInstanceState.class);
	}
}
