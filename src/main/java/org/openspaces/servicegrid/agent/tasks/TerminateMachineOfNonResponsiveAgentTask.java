package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.agent.state.AgentState;

public class TerminateMachineOfNonResponsiveAgentTask extends Task {

	public TerminateMachineOfNonResponsiveAgentTask() {
		super(AgentState.class);
	}

}
