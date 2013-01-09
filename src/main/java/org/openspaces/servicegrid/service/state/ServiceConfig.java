package org.openspaces.servicegrid.service.state;

import java.net.URI;

public class ServiceConfig {

	private String displayName;
	private int numberOfInstances;
	private URI id;

	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}
	
	public String getDisplayName() {
		return displayName;
	}

	public void setNumberOfInstances(int numberOfInstances) {
		this.numberOfInstances = numberOfInstances;
	}
	
	public int getNumberOfInstances() {
		return numberOfInstances;
	}

	public URI getServiceId() {
		return id;
	}

	public void setServiceId(URI id) {
		this.id = id;
	}

}
