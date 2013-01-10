package org.openspaces.servicegrid.service.state;

import java.net.URI;

public class ServiceConfig {

	private String displayName;
	private int plannedNumberOfInstances;
	private URI id;

	public void setDisplayName(String displayName) {
		this.displayName = displayName;
	}
	
	public String getDisplayName() {
		return displayName;
	}

	public void setPlannedNumberOfInstances(int numberOfInstances) {
		this.plannedNumberOfInstances = numberOfInstances;
	}
	
	public int getPlannedNumberOfInstances() {
		return plannedNumberOfInstances;
	}

	public URI getServiceId() {
		return id;
	}

	public void setServiceId(URI id) {
		this.id = id;
	}

}
