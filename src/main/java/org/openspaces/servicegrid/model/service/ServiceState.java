package org.openspaces.servicegrid.model.service;

public class ServiceState {

	private ServiceConfig config;
	private ServiceId id;
	
	public ServiceConfig getConfig() {
		return config;
	}

	public ServiceId getId() {
		return id;
	}

	public void setConfig(ServiceConfig config) {
		this.config = config;
	}

	public void setId(ServiceId id) {
		this.id = id;
	}
}
