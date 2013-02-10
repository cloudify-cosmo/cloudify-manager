package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceGridCapacityPlannerState;
import org.openspaces.servicegrid.service.state.ServiceScalingRule;

public class ScalingRulesTask extends Task {

	public ScalingRulesTask() {
		super(ServiceGridCapacityPlannerState.class);
	}
	
	private ServiceScalingRule scalingRule;
	
	public ServiceScalingRule getScalingRule() {
		return scalingRule;
	}
	
	public void setScalingRule(ServiceScalingRule scalingRule) {
		this.scalingRule = scalingRule;
	}
}
