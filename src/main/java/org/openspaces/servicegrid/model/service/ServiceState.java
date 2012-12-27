package org.openspaces.servicegrid.model.service;

import java.net.URL;
import java.util.Set;

import org.openspaces.servicegrid.ServiceConfig;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;

import com.google.common.collect.Sets;

public class ServiceState extends TaskExecutorState {
	private Set<URL> instancesIds = Sets.newLinkedHashSet();
	private ServiceConfig serviceConfig;

	public Set<URL> getInstancesIds() {
		return instancesIds;
	}
	
	public void setInstancesIds(Set<URL> instancesIds) {
		this.instancesIds = instancesIds;
	}
	
	public void addInstanceId(URL executorId) {
		instancesIds.add(executorId);
	}

	public void setServiceConfig(ServiceConfig serviceConfig) {
		this.serviceConfig = serviceConfig;
	}
	
	public ServiceConfig getServiceConfig() {
		return serviceConfig;
	}
}
