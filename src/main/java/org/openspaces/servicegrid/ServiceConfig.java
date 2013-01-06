package org.openspaces.servicegrid;

import java.net.URL;

public class ServiceConfig {

	private String displayName;
	private int numberOfInstances;
	private URL serviceUrl;

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

	public URL getServiceUrl() {
		return serviceUrl;
	}

	public void setServiceUrl(URL serviceUrl) {
		this.serviceUrl = serviceUrl;
	}

}
