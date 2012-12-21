package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface Orchestrator<S extends TaskExecutorState> extends TaskExecutor<S> {

	Iterable<? extends Task> orchestrate();
}
