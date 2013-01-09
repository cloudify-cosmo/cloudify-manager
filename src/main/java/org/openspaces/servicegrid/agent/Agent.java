package org.openspaces.servicegrid.agent;

import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;

public abstract class Agent {

	public void startServiceInstance(
			StartServiceInstanceTask task, TaskExecutorStateModifier impersonatedStateModifier){};

	public void installServiceInstance(
			InstallServiceInstanceTask task, TaskExecutorStateModifier impersonatedStateModifier){};

}