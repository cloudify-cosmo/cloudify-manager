package org.openspaces.servicegrid;


public interface TaskConsumerStateModifier<T extends TaskConsumerState> {

	void put(T state);

	T get();
}
