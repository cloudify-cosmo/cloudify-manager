package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.agent.state.AgentState;

public class TerminateMachineOfNonResponsiveAgentTask extends ImpersonatingTask {

	public TerminateMachineOfNonResponsiveAgentTask() {
		super(AgentState.class);
	}

}
