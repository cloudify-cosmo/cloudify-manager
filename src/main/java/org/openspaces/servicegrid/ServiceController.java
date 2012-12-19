package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.ServiceConfig;
import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceState;
import org.openspaces.servicegrid.model.Task;

public class ServiceController {

	private final TaskBroker taskBroker;
	private final ServiceStateViewer stateViewer;
	
	public ServiceController(TaskBrokerProvider taskBrokerProvider, ServiceStateViewer stateViewer) {
		this.taskBroker = taskBrokerProvider.getTaskBroker(null);
		this.stateViewer = stateViewer;
	}
	
	public ServiceId installService(ServiceConfig serviceConfig) {
		
		ServiceId serviceId = new ServiceId();
		serviceId.setServiceName(serviceConfig.getName());
		
		Task installServiceTask = new Task();
		installServiceTask.setType("install-service");
		installServiceTask.setTarget("serviceOrchestrator");
		installServiceTask.setProperty("service-id", serviceId);
		installServiceTask.setProperty("service-config", serviceConfig);
		taskBroker.addTask(installServiceTask);
		
		return serviceId;
	}

	public ServiceState getServiceStatus(ServiceId serviceId) {
		
		return stateViewer.getServiceState(serviceId);
	}
}
