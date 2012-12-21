package org.openspaces.servicegrid;

import java.net.URL;

import org.openspaces.servicegrid.model.service.AggregatedServiceState;
import org.openspaces.servicegrid.model.service.ServiceConfig;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.tasks.SetServiceConfigTask;

public class ServiceController {

	private final TaskBroker taskBroker;
	private final StateViewer stateViewer;
	private URL targetExecutorId;
	
	public ServiceController(TaskBrokerProvider taskBrokerProvider, StateViewer stateViewer, URL targetExecutorId) {
		this.taskBroker = taskBrokerProvider.getTaskBroker(null);
		this.stateViewer = stateViewer;
		this.targetExecutorId = targetExecutorId;
		
	}
	
	public URL installService(ServiceConfig serviceConfig) {
		
		SetServiceConfigTask installServiceTask = new SetServiceConfigTask();
		installServiceTask.setTarget(targetExecutorId);
		installServiceTask.setServiceConfig(serviceConfig);
		taskBroker.postTask(installServiceTask);
		
		return targetExecutorId;
	}


	public AggregatedServiceState getServiceState(URL serviceId) {
		AggregatedServiceState state = new AggregatedServiceState();
		ServiceOrchestratorState orchestratorState = (ServiceOrchestratorState) stateViewer.getTaskExecutorState(targetExecutorId);
		state.setServiceConfig(orchestratorState.getConfig());
		
		for (URL instanceId : orchestratorState.getInstanceIds()) {
			ServiceInstanceState instanceState = (ServiceInstanceState) stateViewer.getTaskExecutorState(instanceId);
			state.addInstance(instanceId, instanceState);
		}
		
		return state;
				
	}

	public ServiceInstanceState getServiceInstanceState(URL instanceId) {
		return (ServiceInstanceState) stateViewer.getTaskExecutorState(instanceId);
	}
}
