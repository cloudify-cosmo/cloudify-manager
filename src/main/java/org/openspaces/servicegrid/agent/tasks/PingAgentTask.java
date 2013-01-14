package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;


public class PingAgentTask extends Task {


	private Integer expectedNumberOfRestartsInAgentState;

	/**
	 * @return the number of restarts the agent had when the ping task was constructed
	 */
	public Integer getExpectedNumberOfRestartsInAgentState() {
		return expectedNumberOfRestartsInAgentState;
	}

	public void setExpectedNumberOfRestartsInAgentState(Integer expectedNumberOfRestartsInAgentState) {
		this.expectedNumberOfRestartsInAgentState = expectedNumberOfRestartsInAgentState;
	}
}
