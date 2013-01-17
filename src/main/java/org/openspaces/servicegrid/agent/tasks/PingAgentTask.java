package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;


public class PingAgentTask extends Task {


	private Integer expectedNumberOfAgentRestartsInAgentState;
	private Integer expectedNumberOfMachineRestartsInAgentState;

	/**
	 * @return the number of restarts the agent had when the ping task was constructed
	 */
	public Integer getExpectedNumberOfAgentRestartsInAgentState() {
		return expectedNumberOfAgentRestartsInAgentState;
	}

	public void setExpectedNumberOfAgentRestartsInAgentState(Integer expectedNumberOfAgentRestartsInAgentState) {
		this.expectedNumberOfAgentRestartsInAgentState = expectedNumberOfAgentRestartsInAgentState;
	}

	public Integer getExpectedNumberOfMachineRestartsInAgentState() {
		return expectedNumberOfMachineRestartsInAgentState;
	}

	/**
	 * @return the number of restarts the machine had when the ping task was constructed
	 */
	public void setExpectedNumberOfMachineRestartsInAgentState(
			Integer expectedNumberOfMachineRestartsInAgentState) {
		this.expectedNumberOfMachineRestartsInAgentState = expectedNumberOfMachineRestartsInAgentState;
	}
}
