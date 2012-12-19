package org.openspaces.servicegrid;

import java.util.Map;

import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceState;

import com.google.common.collect.Maps;

public class MapServiceStateHolder implements ServiceStateHolder {

	private final Map<ServiceId, ServiceState> servicesState = Maps.newConcurrentMap();
	
	public ServiceState getServiceState(ServiceId serviceId) {
		return servicesState.get(serviceId);
	}

	public void updateServiceState(ServiceId serviceId,
			ServiceState serviceState) {
		servicesState.put(serviceId, serviceState);
	}

}
