package org.openspaces.servicegrid.agent.tasks;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.agent.state.AgentState;

public class PlanAgentTask  extends Task {

	public PlanAgentTask() {
		super(AgentState.class);
	}

	private List<URI> serviceInstanceIds;
	public List<URI> getServiceInstanceIds() {
		return this.serviceInstanceIds;
	}

	public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
		this.serviceInstanceIds = serviceInstanceIds;
	}
}
