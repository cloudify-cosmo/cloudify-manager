package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.ImpersonatingTask;
import org.openspaces.servicegrid.agent.state.AgentState;

public class TerminateMachineTask  extends ImpersonatingTask {

	public TerminateMachineTask() {
		super(AgentState.class);
	}
}
