package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.StartServiceInstanceTask;

public abstract class Agent {

	public void startServiceInstance(
			StartServiceInstanceTask task, TaskExecutorStateModifier impersonatedStateModifier){};

	public void installServiceInstance(
			InstallServiceInstanceTask task, TaskExecutorStateModifier impersonatedStateModifier){};

}