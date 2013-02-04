package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.agent.state.AgentState;

public class MarkAgentAsStoppingTask extends Task {

	public MarkAgentAsStoppingTask() {
		super(AgentState.class);
	}
	
}
