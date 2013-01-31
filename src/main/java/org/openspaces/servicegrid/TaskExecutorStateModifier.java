package org.openspaces.servicegrid;


public interface TaskExecutorStateModifier<T extends TaskConsumerState> {

	void updateState(T impersonatedState);

	T getState(Class<? extends T> clazz);
}
