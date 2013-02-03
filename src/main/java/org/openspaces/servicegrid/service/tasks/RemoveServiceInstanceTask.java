package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.service.state.ServiceState;

public class RemoveServiceInstanceTask extends ImpersonatingTask {

	public RemoveServiceInstanceTask() {
		super(ServiceState.class);
	}

	private URI instanceId;

	public URI getInstanceId() {
		return instanceId;
	}

	public void setInstanceId(URI instanceId) {
		this.instanceId = instanceId;
	}

}
