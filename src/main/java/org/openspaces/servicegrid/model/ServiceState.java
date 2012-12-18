package org.openspaces.servicegrid.model;


public class ServiceState {

	private ServiceConfig config;
	private ServiceId id;

	public ServiceConfig getConfig() {
		return config;
	}

	public ServiceId getId() {
		return id;
	}

	public Event getLastEvent() {
		return null;
	}

	public void setConfig(ServiceConfig config) {
		this.config = config;
	}

	public void setId(ServiceId id) {
		this.id = id;
	}

	/*public State getState() {
		// TODO XML: Auto-generated method stub
		return null;
	}*/
	
}
