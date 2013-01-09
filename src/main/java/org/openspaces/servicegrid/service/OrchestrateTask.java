package org.openspaces.servicegrid.service;

import org.openspaces.servicegrid.service.tasks.ServiceTask;

public class OrchestrateTask extends ServiceTask {

	private int maxNumberOfOrchestrationSteps;

	public int getMaxNumberOfOrchestrationSteps() {
		return maxNumberOfOrchestrationSteps;
	}

	public void setMaxNumberOfOrchestrationSteps(
			int maxNumberOfOrchestrationSteps) {
		this.maxNumberOfOrchestrationSteps = maxNumberOfOrchestrationSteps;
	}
}
