package org.openspaces.servicegrid.service;

import java.util.Set;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceConfig;

public class FloorPlanTask extends Task {

	private Set<ServiceConfig> services;

	public Set<ServiceConfig> getServices() {
		return services;
	}

	public void setServices(Set<ServiceConfig> services) {
		this.services = services;
				
	}

}
