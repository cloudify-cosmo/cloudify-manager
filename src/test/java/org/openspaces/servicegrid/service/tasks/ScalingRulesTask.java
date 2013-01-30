package org.openspaces.servicegrid.service.tasks;

import java.net.URI;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceScalingRule;

public class ScalingRulesTask extends Task {

	private ServiceScalingRule scalingRule;
	private URI serviceId;
	
	public ServiceScalingRule getScalingRule() {
		return scalingRule;
	}
	
	public void setScalingRule(ServiceScalingRule scalingRule) {
		this.scalingRule = scalingRule;
	}
	
	public URI getServiceId() {
		return serviceId;
	}
	
	public void setServiceId(URI serviceId) {
		this.serviceId = serviceId;
	}
}
