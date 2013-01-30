package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

public class ServiceGridCapacityPlannerState extends TaskConsumerState {

	private Map<URI, ServiceScalingRule> scalingRuleByService = Maps.newLinkedHashMap();

	public Map<URI, ServiceScalingRule> getScalingRuleByService() {
		return scalingRuleByService;
	}
	
	public void setScalingRuleByService(Map<URI, ServiceScalingRule> scalingRuleByService) {
		this.scalingRuleByService = Maps.newLinkedHashMap();
		scalingRuleByService.putAll(scalingRuleByService);
	}

	@JsonIgnore
	public void addServiceScalingRule(URI serviceId, ServiceScalingRule scalingRule) {
		scalingRuleByService.put(serviceId, scalingRule);
	}
	
	@JsonIgnore
	public void removeServiceScalingRule(URI serviceId) {
		Preconditions.checkArgument(scalingRuleByService.containsKey(serviceId));
		scalingRuleByService.remove(serviceId);
	}
}