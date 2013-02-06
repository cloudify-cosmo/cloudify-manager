package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceState;

public class RemoveServiceInstanceFromServiceTask extends Task {

	public RemoveServiceInstanceFromServiceTask() {
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
