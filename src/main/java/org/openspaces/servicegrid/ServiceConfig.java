package org.openspaces.servicegrid;

public class ServiceConfig {

	private String displayName;
	private int numberOfInstances;

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

}
