package org.openspaces.servicegrid;

import java.net.URL;

public interface TaskBrokerProvider {
	
	TaskBroker getTaskBroker(URL executorId);
}
