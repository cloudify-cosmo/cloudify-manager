package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.agent.state.AgentState;

public class TerminateMachineTask  extends Task {

	public TerminateMachineTask() {
		super(AgentState.class);
	}
}
