package org.openspaces.servicegrid.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlan;
import org.openspaces.servicegrid.service.state.ServiceGridPlannerState;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleOutServiceTask;
import org.openspaces.servicegrid.service.tasks.UpdateDeploymentPlanTask;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridDeploymentPlanner {

	private final ServiceGridPlannerState state;
	private final URI orchestratorId;
	private final ObjectMapper mapper = StreamUtils.newJsonObjectMapper();
		
	public ServiceGridDeploymentPlanner(ServiceGridPlannerParameter parameterObject) {
		this.orchestratorId = parameterObject.getOrchestratorId();
		this.state = new ServiceGridPlannerState();
		this.state.setDeploymentPlan(new ServiceGridDeploymentPlan());
	}

	@TaskConsumer(persistTask = true)
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

	@TaskConsumer(persistTask = true)
	public void installService(InstallServiceTask task) {
		
		ServiceConfig serviceConfig = task.getServiceConfig();
		Preconditions.checkNotNull(serviceConfig);
		fixServiceId(serviceConfig);
		boolean installed = isServiceInstalled(serviceConfig.getServiceId());
		Preconditions.checkState(!installed);
		state.addService(serviceConfig);
	}

	@TaskProducer	
	public Iterable<Task> deploymentPlan() {
		
		List<Task> newTasks = Lists.newArrayList();
		if (state.isDeploymentPlanningRequired()) {
			updateDeploymentPlan();
			
			UpdateDeploymentPlanTask enforceTask = new UpdateDeploymentPlanTask();
			enforceTask.setTarget(orchestratorId);
			enforceTask.setDeploymentPlan(state.getDeploymentPlan());
			addNewTask(newTasks, enforceTask);
			
			state.setDeploymentPlanningRequired(false);
		}
		return newTasks;
	}

	private ServiceGridDeploymentPlan updateDeploymentPlan() {
		
		ServiceGridDeploymentPlan deploymentPlan = state.getDeploymentPlan();
		
		for (final ServiceConfig newService : state.getServices()) {
			final ServiceConfig oldService = deploymentPlan.getServiceById(newService.getServiceId());
			deploymentPlanUpdateService(deploymentPlan, oldService, newService);
				
			final URI serviceId = newService.getServiceId();
			
			int oldNumberOfInstances = oldService == null ? 0 : oldService.getPlannedNumberOfInstances();
			int newNumberOfInstances = newService.getPlannedNumberOfInstances();
			for (int i = newNumberOfInstances - oldNumberOfInstances; i > 0; i--) {
				
				final URI instanceId = newInstanceId(serviceId);
				final URI agentId = newAgentExecutorId();
				deploymentPlan.addServiceInstance(serviceId, agentId, instanceId);
			}
		}
		return deploymentPlan;
	}

	private void deploymentPlanUpdateService(ServiceGridDeploymentPlan deploymentPlan, ServiceConfig oldService, ServiceConfig newService) {
		
		if (oldService == null) {
			deploymentPlanAddServiceClone(deploymentPlan, newService);
		}
		else if (!StreamUtils.elementEquals(mapper, newService,oldService)) {
			deploymentPlan.removeService(oldService);
			deploymentPlanAddServiceClone(deploymentPlan, newService);
		}
	}

	private void deploymentPlanAddServiceClone(
			ServiceGridDeploymentPlan deploymentPlan,
			ServiceConfig service) {
		
		final ServiceConfig serviceClone = StreamUtils.cloneElement(mapper, service);
		deploymentPlan.addService(serviceClone);
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
		return newURI(serviceId.toString() + "instances/" + state.getAndIncrementNextServiceInstanceIndex(serviceId) +"/");
	}

	private URI newAgentExecutorId() {
		return newURI("http://localhost/agent/" + state.getAndIncrementNextAgentIndex()+"/");
	}
	
	private URI newURI(String URI) {
		try {
			return new URI(URI);
		} catch (final URISyntaxException e) {
			throw Throwables.propagate(e);
		}
	}

	@TaskConsumerStateHolder
	public TaskConsumerState getState() {
		return state;
	}

	private static void addNewTask(List<Task> newTasks, final Task task) {
		newTasks.add(task);
	}
}
