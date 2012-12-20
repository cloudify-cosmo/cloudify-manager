package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;

import org.openspaces.servicegrid.model.service.ServiceConfig;
import org.openspaces.servicegrid.model.service.ServiceId;
import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.service.ServiceState;
import org.openspaces.servicegrid.model.tasks.InstallServiceTask;

import com.google.common.base.Throwables;

public class ServiceController {

	private final TaskBroker taskBroker;
	private final StateViewer stateViewer;
	private URL executorId;
	
	public ServiceController(TaskBrokerProvider taskBrokerProvider, StateViewer stateViewer) {
		this.taskBroker = taskBrokerProvider.getTaskBroker(null);
		this.stateViewer = stateViewer;
		try {
			this.executorId = new URL("http://localhost/executors/service-orchestrator");
		} catch (MalformedURLException e) {
			Throwables.propagate(e);
		}
	}
	
	public ServiceId installService(ServiceConfig serviceConfig) {
		
		ServiceId serviceId = new ServiceId();
		serviceId.setServiceName(serviceConfig.getName());
				
		InstallServiceTask installServiceTask = new InstallServiceTask();
		installServiceTask.setTarget(executorId);
		installServiceTask.setServiceId(serviceId);
		installServiceTask.setServiceConfig(serviceConfig);
		taskBroker.postTask(installServiceTask);
		
		return serviceId;
	}

	public ServiceState getServiceState(ServiceId serviceId) {

		ServiceState serviceState = null;
		
		ServiceOrchestratorState taskExecutorState = (ServiceOrchestratorState) stateViewer.getTaskExecutorState(executorId);
		if (taskExecutorState != null) {
			serviceState = taskExecutorState.getServiceState(serviceId);
		}
		return serviceState;
	}
}
