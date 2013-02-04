package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.agent.state.AgentState;

public class StartMachineTask extends Task {

	public StartMachineTask() {
		super(AgentState.class);
	}
}
