package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

public interface TaskExecutorStateModifier {

	void updateState(TaskExecutorState impersonatedState);

	<T extends TaskExecutorState> T getState();
}
