package org.openspaces.servicegrid.service;

import java.util.Set;

import org.openspaces.servicegrid.TaskProducerTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;

public class FloorPlanTask extends TaskProducerTask {

	private Set<ServiceConfig> services;

	public Set<ServiceConfig> getServices() {
		return services;
	}

	public void setServices(Set<ServiceConfig> services) {
		this.services = services;
				
	}

}
