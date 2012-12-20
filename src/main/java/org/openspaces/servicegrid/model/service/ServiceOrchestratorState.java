package org.openspaces.servicegrid.model.service;

import java.util.Map;

import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Maps;

public class ServiceOrchestratorState extends TaskExecutorState {

	Map<ServiceId, ServiceState> serviceStateById = Maps.newHashMap();

	public ServiceState getServiceState(ServiceId serviceId) {
		return serviceStateById.get(serviceId);
	}

	public void putServiceState(ServiceId serviceId, ServiceState serviceConfig) {
		serviceStateById.put(serviceId, serviceConfig);
	}
}
