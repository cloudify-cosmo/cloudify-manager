package org.openspaces.servicegrid.service.tasks;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.service.state.ServiceGridFloorPlan;

public class EnforceNewFloorPlanTask extends Task {

	private ServiceGridFloorPlan floorPlan;

	public ServiceGridFloorPlan getFloorPlan() {
		return floorPlan;
	}

	public void setFloorPlan(ServiceGridFloorPlan floorPlan) {
		this.floorPlan = floorPlan;
	}

}
