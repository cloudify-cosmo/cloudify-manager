package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.agent.state.AgentState;

public class RemoveServiceInstanceFromAgentTask extends Task {
	
	private URI instanceId;

	public RemoveServiceInstanceFromAgentTask() {
		super(AgentState.class);
	}

	public URI getInstanceId() {
		return instanceId;
	}

	public void setInstanceId(URI instanceId) {
		this.instanceId = instanceId;
	}
}
