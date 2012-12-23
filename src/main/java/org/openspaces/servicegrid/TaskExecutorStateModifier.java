package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceInstanceState;

public interface TaskExecutorStateModifier {

	void updateState(ServiceInstanceState impersonatedState);
}
