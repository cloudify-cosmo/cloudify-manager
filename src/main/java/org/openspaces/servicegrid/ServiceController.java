package org.openspaces.servicegrid;

import org.openspaces.servicegrid.model.ServiceConfig;
import org.openspaces.servicegrid.model.ServiceId;
import org.openspaces.servicegrid.model.ServiceStatus;
import org.openspaces.servicegrid.model.Task;

import com.google.common.base.Objects;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import com.google.common.collect.Sets;

public class ServiceController {

	private final TaskBroker taskBroker;
	
	public ServiceController(TaskBroker taskBroker) {
		this.taskBroker = taskBroker;
	}
	
	public ServiceId installService(ServiceConfig serviceConfig) {
		
		ServiceId serviceId = new ServiceId();
		serviceId.setServiceName(serviceConfig.getName());
		
		Task installServiceTask = new Task();
		installServiceTask.setType("install-service");
		installServiceTask.setTags(Sets.newHashSet(serviceId.toString()));
		installServiceTask.setProperty("service-id", serviceId);
		installServiceTask.setProperty("service-config", serviceConfig);
		taskBroker.addTask(installServiceTask);
		
		return serviceId;
	}

	public ServiceStatus getServiceStatus(ServiceId serviceId) {
		
		Iterable<Task> tasks = taskBroker.getTasksByTag(serviceId.toString());
		
		ServiceStatus status = new ServiceStatus();
		status.setId(serviceId);
		Task task = Iterables.get(tasks, 0);
		if (task != null) {
			
			ServiceId actualServiceId = task.getProperty("service-id", ServiceId.class);
			Preconditions.checkState(
					Objects.equal(serviceId.toString(),actualServiceId.toString()),
					"Task service-id expected to be %s, actual service-id is %s", serviceId, actualServiceId);
			
			status.setConfig(task.getProperty("service-config", ServiceConfig.class));
		}
		return status;
	}
}
