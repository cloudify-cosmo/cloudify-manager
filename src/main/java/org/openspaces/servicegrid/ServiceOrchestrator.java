package org.openspaces.servicegrid;

import java.util.ArrayList;

import org.openspaces.servicegrid.model.ServiceConfig;
import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceState;
import org.openspaces.servicegrid.model.Task;

import com.google.common.collect.Lists;

public class ServiceOrchestrator implements Orchestrator {

	private final ServiceStateHolder stateHolder;

	public ServiceOrchestrator(ServiceStateHolder stateHolder) {
		this.stateHolder = stateHolder;
	}

	public Iterable<Task> orchestrate(Iterable<Task> tasks) {
		
		ArrayList<Task> newTasks = Lists.newArrayList();
		
		for (Task task : tasks) {
			if ("install-service".equals(task.getType())){
				ServiceState serviceState = new ServiceState();
				serviceState.setId(task.getProperty("service-id", ServiceId.class));
				serviceState.setConfig(task.getProperty("service-config", ServiceConfig.class));
				stateHolder.updateServiceState(serviceState.getId(), serviceState);
			}
		}
		
		return newTasks;
	}

}
