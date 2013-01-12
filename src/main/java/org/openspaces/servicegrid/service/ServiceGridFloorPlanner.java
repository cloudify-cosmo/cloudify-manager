package org.openspaces.servicegrid.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.UUID;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridFloorPlan;
import org.openspaces.servicegrid.service.state.ServiceGridPlannerState;
import org.openspaces.servicegrid.service.tasks.EnforceNewFloorPlanTask;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleOutServiceTask;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridFloorPlanner {

	private final ServiceGridPlannerState state;
	private final URI orchestratorId;
	private final ObjectMapper mapper = StreamUtils.newJsonObjectMapper();
	
	public ServiceGridFloorPlanner(ServiceGridPlannerParameter parameterObject) {
		this.orchestratorId = parameterObject.getOrchestratorId();
		this.state = new ServiceGridPlannerState();
		this.state.setFloorPlan(new ServiceGridFloorPlan());
	}

	@TaskConsumer
	public void scaleOutService(ScaleOutServiceTask task) {
		
		for (ServiceConfig serviceConfig : state.getServices()) {
			if (serviceConfig.getServiceId().equals(task.getServiceId())) {
				int newPlannedNumberOfInstances = task.getPlannedNumberOfInstances();
				if (serviceConfig.getPlannedNumberOfInstances() != newPlannedNumberOfInstances) {
					serviceConfig.setPlannedNumberOfInstances(newPlannedNumberOfInstances);
					state.updateService(serviceConfig);
					return;
				}
			}
		}
		Preconditions.checkArgument(false,"Cannot find service %s", task.getServiceId());
	}

	@TaskConsumer
	public void installService(InstallServiceTask task) {
		ServiceConfig serviceConfig = task.getServiceConfig();
		fixServiceId(serviceConfig);
		boolean installed = isServiceInstalled(serviceConfig.getServiceId());
		Preconditions.checkState(!installed);
		Preconditions.checkNotNull(serviceConfig);
		state.addService(serviceConfig);
	}

	@TaskProducer	
	public Iterable<Task> floorPlan() {
		
		List<Task> newTasks = Lists.newArrayList();
		if (state.isFloorPlanningRequired()) {
			updateFloorPlan();
			EnforceNewFloorPlanTask enforceTask = new EnforceNewFloorPlanTask();
			enforceTask.setTarget(orchestratorId);
			enforceTask.setFloorPlan(state.getFloorPlan());
			addNewTask(newTasks, enforceTask);
			
			state.setFloorPlanningRequired(false);
		}
		return newTasks;
	}

	private ServiceGridFloorPlan updateFloorPlan() {
		
		ServiceGridFloorPlan floorPlan = state.getFloorPlan();
		
		for (final ServiceConfig newService : state.getServices()) {
			final ServiceConfig oldService = floorPlan.getServiceById(newService.getServiceId());
			floorPlanUpdateService(floorPlan, oldService, newService);
				
			final URI serviceId = newService.getServiceId();
			
			int oldNumberOfInstances = oldService == null ? 0 : oldService.getPlannedNumberOfInstances();
			int newNumberOfInstances = newService.getPlannedNumberOfInstances();
			for (int i = newNumberOfInstances - oldNumberOfInstances; i > 0; i--) {
				
				final URI instanceId = newInstanceId(serviceId);
				final URI agentId = newAgentExecutorId();
				floorPlan.addServiceInstance(serviceId, agentId, instanceId);
			}
		}
		return floorPlan;
	}

	private void floorPlanUpdateService(ServiceGridFloorPlan floorPlan, ServiceConfig oldService, ServiceConfig newService) {
		
		if (oldService == null) {
			floorPlanAddServiceClone(floorPlan, newService);
		}
		else if (!StreamUtils.elementEquals(mapper, newService,oldService)) {
			floorPlan.removeService(oldService);
			floorPlanAddServiceClone(floorPlan, newService);
		}
	}

	private void floorPlanAddServiceClone(
			ServiceGridFloorPlan floorPlan,
			ServiceConfig service) {
		
		final ServiceConfig serviceClone = StreamUtils.cloneElement(mapper, service);
		floorPlan.addService(serviceClone);
	}

	
	private void fixServiceId(ServiceConfig serviceConfig) {
		if (!serviceConfig.getServiceId().toString().endsWith("/")) {
			try {
				serviceConfig.setServiceId(new URI(serviceConfig.getServiceId()+"/"));
			} catch (URISyntaxException e) {
				throw Throwables.propagate(e);
			}
		}
	}

	private boolean isServiceInstalled(final URI serviceId) {
		return Iterables.tryFind(state.getServices(), new Predicate<ServiceConfig>() {

			@Override
			public boolean apply(ServiceConfig serviceConfig) {
				return serviceConfig.getServiceId().equals(serviceId);
			}
		}).isPresent();
	}
	
	private URI newInstanceId(URI serviceId) {
		Preconditions.checkArgument(serviceId.toString().endsWith("/"),"service id " + serviceId + " must end with slash");
		return newURI(serviceId.toString() + "instances/" + UUID.randomUUID() +"/");
	}

	private URI newAgentExecutorId() {
		return newURI("http://localhost/agent/" + UUID.randomUUID()+"/");
	}
	
	private URI newURI(String URI) {
		try {
			return new URI(URI);
		} catch (final URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}
	
	public TaskConsumerState getState() {
		return state;
	}

	private static void addNewTask(List<Task> newTasks, final Task task) {
		newTasks.add(task);
	}

}
