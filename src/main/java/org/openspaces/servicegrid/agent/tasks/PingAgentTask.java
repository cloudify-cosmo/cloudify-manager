package org.openspaces.servicegrid.agent.tasks;

import org.openspaces.servicegrid.Task;


public class PingAgentTask extends Task {


	private int numberOfRestarts;

	/**
	 * @return the number of restarts the agent had when the ping task was constructed
	 */
	public int getNumberOfRestarts() {
		return numberOfRestarts;
	}

	public void setNumberOfRestarts(int numberOfRestarts) {
		this.numberOfRestarts = numberOfRestarts;
	}
}
