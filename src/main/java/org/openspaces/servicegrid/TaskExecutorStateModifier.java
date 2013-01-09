package org.openspaces.servicegrid;


public interface TaskExecutorStateModifier {

	void updateState(TaskExecutorState impersonatedState);

	<T extends TaskExecutorState> T getState();
}
