package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;

public class ScalingRulesTask extends Task {

	private String valueName;
	private Object valueThreshold;

	public void setValueName(String valueName) {
		this.valueName = valueName;
	}
	
	public String getValueName() {
		return valueName;
	}

	public void setValueThreshold(Object valueThreshold) {
		this.valueThreshold = valueThreshold;
	}
	
	public Object getValueThreshold() {
		return valueThreshold;
	}
}
