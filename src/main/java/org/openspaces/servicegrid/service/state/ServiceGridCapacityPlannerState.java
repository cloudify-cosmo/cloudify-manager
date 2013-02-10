package org.openspaces.servicegrid.service.state;

import java.net.URI;
import java.util.List;

import org.openspaces.servicegrid.TaskConsumerState;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridCapacityPlannerState extends TaskConsumerState {

	private List<ServiceScalingRule> scalingRules = Lists.newArrayList();

	public List<ServiceScalingRule> getScalingRules() {
		return scalingRules;
	}
	
	public void setScalingRules(List<ServiceScalingRule> scalingRules) {
		this.scalingRules = scalingRules;
	}

	@JsonIgnore
	public void addServiceScalingRule(ServiceScalingRule scalingRule) {
		removeServiceScalingRule(scalingRule.getServiceId());
		scalingRules.add(scalingRule);
	}
	
	@JsonIgnore
	public boolean removeServiceScalingRule(URI serviceId) {
		return Iterables.removeIf(scalingRules, findServiceIdPredicate(serviceId));
	}

	private Predicate<ServiceScalingRule> findServiceIdPredicate(final URI serviceId) {
		Preconditions.checkNotNull(serviceId);
		
		return new Predicate<ServiceScalingRule>() {

			@Override
			public boolean apply(ServiceScalingRule rule) {
				return serviceId.equals(rule.getServiceId());
			}
		};
	}


}