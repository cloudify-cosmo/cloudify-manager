package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.ImpersonatingTask;

public class RemoveServiceInstanceTask extends ImpersonatingTask {

	private URI instanceId;

	public URI getInstanceId() {
		return instanceId;
	}

	public void setInstanceId(URI instanceId) {
		this.instanceId = instanceId;
	}

}
