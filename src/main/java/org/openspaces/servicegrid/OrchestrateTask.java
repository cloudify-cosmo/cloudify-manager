package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceTask;

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
