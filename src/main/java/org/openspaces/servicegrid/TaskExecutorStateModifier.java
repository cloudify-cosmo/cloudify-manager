package org.openspaces.servicegrid;


public interface TaskExecutorStateModifier {

	void updateState(TaskConsumerState impersonatedState);

	<T extends TaskConsumerState> T getState();
}
