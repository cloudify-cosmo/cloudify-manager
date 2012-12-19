package org.openspaces.servicegrid;

public interface TaskBrokerProvider {
	TaskBroker getTaskBroker(String target);
}
