package org.openspaces.servicegrid;

import org.openspaces.servicegrid.mock.RemoteManagementFailover;


public interface TaskConsumerHistoryModifier {

	void addTaskToHistory(Task task) throws RemoteManagementFailover;
}
