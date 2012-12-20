package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.service.ServiceId;
import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.service.ServiceState;
import org.openspaces.servicegrid.model.tasks.InstallServiceTask;
import org.openspaces.servicegrid.model.tasks.ServiceTask;
import org.openspaces.servicegrid.model.tasks.Task;

public class ServiceOrchestrator implements Orchestrator<ServiceOrchestratorState, ServiceTask> {

	private final ServiceOrchestratorState state;
	//private final StateHolder stateHolder;

	public ServiceOrchestrator(/*StateHolder stateHolder*/) {
		//this.stateHolder = stateHolder;
		this.state = new ServiceOrchestratorState();
	}

	@Override
	public void execute(Task task) {
		
		if (task instanceof InstallServiceTask){
			installService((InstallServiceTask) task);
		}
	}

	private void installService(InstallServiceTask installServiceTask) {
		ServiceId serviceId = installServiceTask.getServiceId();
		
		ServiceState serviceState = state.getServiceState(serviceId);
		if (serviceState != null) {
			throw new IllegalArgumentException(serviceId + " is already installed");
		}
		serviceState = new ServiceState();
		serviceState.setConfig(installServiceTask.getServiceConfig());
		serviceState.setId(installServiceTask.getServiceId());
		state.putServiceState(serviceId, serviceState);
	}
	
	
	@Override
	public Iterable<ServiceTask> orchestrate() {
	
		throw new UnsupportedOperationException();
		/*
		ArrayList<ServiceTask> newTasks = Lists.newArrayList();
		for (ServiceOrchestratorState serviceState : stateHolder.getServices()) {
			StartMachineTask task = new StartMachineTask();
			serviceState.addTask(task);
			newTasks.add(task);
		}
		
		return newTasks;
		*/
	}

	public String getId() {
		return "service-orchestrator";
	}

	@Override
	public ServiceOrchestratorState getState() {
		return state;
	}

}
