package org.openspaces.servicegrid.service;

import java.net.URI;

import org.openspaces.servicegrid.time.CurrentTimeProvider;

public class ServiceGridPlannerParameter {
	
	private CurrentTimeProvider timeProvider;
	private URI orchestratorId;
	
	public CurrentTimeProvider getTimeProvider() {
		return timeProvider;
	}

	public void setTimeProvider(CurrentTimeProvider timeProvider) {
		this.timeProvider = timeProvider;
	}

	public URI getOrchestratorId() {
		return orchestratorId;
	}

	public void setOrchestratorId(URI orchestratorId) {
		this.orchestratorId = orchestratorId;
	}
	
}
