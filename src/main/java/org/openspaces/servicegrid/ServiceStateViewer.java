package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceState;

public interface ServiceStateViewer {

	ServiceState getServiceState(ServiceId serviceId);

}
