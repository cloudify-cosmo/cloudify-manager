package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.Task;

public interface Orchestrator {

	Iterable<Task> orchestrate(Iterable<Task> tasks);

}
