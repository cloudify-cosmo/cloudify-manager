package org.openspaces.servicegrid.service.state;

import java.net.URI;

public class ServiceScalingRule {

	private String propertyName;
	private Object highThreshold;
	private Object lowThreshold;
	private URI serviceId;
	
	public void setPropertyName(String valueName) {
		this.propertyName = valueName;
	}

	public void setHighThreshold(Object highThreshold) {
		this.highThreshold = highThreshold;
	}
	
	public String getPropertyName() {
		return propertyName;
	}
	
	public Object getHighThreshold() {
		return highThreshold;
	}

	public Object getLowThreshold() {
		return lowThreshold;
	}

	public void setLowThreshold(Object lowThreshold) {
		this.lowThreshold = lowThreshold;
	}

	public URI getServiceId() {
		return serviceId;
	}

	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}

}
