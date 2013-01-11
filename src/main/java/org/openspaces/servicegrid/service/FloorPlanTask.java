package org.openspaces.servicegrid.service;

import java.util.Set;

import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.tasks.ServiceTask;

public class FloorPlanTask extends ServiceTask {

	private Set<ServiceConfig> services;

	public Set<ServiceConfig> getServices() {
		return services;
	}

	public void setServices(Set<ServiceConfig> services) {
		this.services = services;
				
	}

}
