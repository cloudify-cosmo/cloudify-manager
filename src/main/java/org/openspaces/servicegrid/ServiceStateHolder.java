package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceState;

public interface ServiceStateHolder extends ServiceStateViewer {

	void updateServiceState(ServiceId serviceId, ServiceState serviceState);

}
