package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface StateHolder extends StateViewer {

	void putTaskExecutorState(URL executorId, TaskExecutorState state);

}
