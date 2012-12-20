package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface StateViewer {

	TaskExecutorState getTaskExecutorState(URL executorId);

}
