package org.openspaces.servicegrid.service;

import org.openspaces.servicegrid.Task;

public class OrchestrateTask extends Task {

	private int maxNumberOfOrchestrationSteps = 1;

	public int getMaxNumberOfOrchestrationSteps() {
		return maxNumberOfOrchestrationSteps;
	}

	public void setMaxNumberOfOrchestrationSteps(
			int maxNumberOfOrchestrationSteps) {
		this.maxNumberOfOrchestrationSteps = maxNumberOfOrchestrationSteps;
	}
}
