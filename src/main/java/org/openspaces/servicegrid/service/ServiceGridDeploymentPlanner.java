package org.openspaces.servicegrid.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.Set;

import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlan;
import org.openspaces.servicegrid.service.state.ServiceGridDeploymentPlannerState;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleServiceTask;
import org.openspaces.servicegrid.service.tasks.UninstallServiceTask;
import org.openspaces.servicegrid.service.tasks.UpdateDeploymentPlanTask;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Sets;

public class ServiceGridDeploymentPlanner {

	private final ServiceGridDeploymentPlannerState state;
	private final URI orchestratorId;
	private final ObjectMapper mapper = StreamUtils.newJsonObjectMapper();
		
	public ServiceGridDeploymentPlanner(ServiceGridDeploymentPlannerParameter parameterObject) {
		this.orchestratorId = parameterObject.getOrchestratorId();
		this.state = new ServiceGridDeploymentPlannerState();
		this.state.setDeploymentPlan(new ServiceGridDeploymentPlan());
	}

	@TaskConsumer(persistTask = true)
	public void scaleService(ScaleServiceTask task) {
		
		URI serviceId = task.getServiceId();
		ServiceConfig serviceConfig = state.getServiceById(serviceId);
		Preconditions.checkNotNull(serviceConfig, "Cannot find service %s", serviceId);
		
		int newPlannedNumberOfInstances = task.getPlannedNumberOfInstances();
		if (serviceConfig.getPlannedNumberOfInstances() != newPlannedNumberOfInstances) {
			serviceConfig.setPlannedNumberOfInstances(newPlannedNumberOfInstances);
			state.updateService(serviceConfig);
		}
	}

	@TaskConsumer(persistTask = true)
	public void installService(InstallServiceTask task) {
		
		final ServiceConfig serviceConfig = task.getServiceConfig();
		Preconditions.checkNotNull(serviceConfig);
		final URI serviceId = serviceConfig.getServiceId();
		checkServiceId(serviceId);
		boolean installed = isServiceInstalled(serviceId);
		Preconditions.checkState(!installed);
		state.addService(serviceConfig);
	}

	@TaskConsumer(persistTask = true)
	public void uninstallService(UninstallServiceTask task) {
		URI serviceId = task.getServiceId();
		checkServiceId(serviceId);
		boolean installed = isServiceInstalled(serviceId);
		Preconditions.checkState(installed);
		state.removeService(serviceId);
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
			if (newNumberOfInstances > oldNumberOfInstances) {
				for (int i = newNumberOfInstances - oldNumberOfInstances; i > 0; i--) {
					
					final URI instanceId = newInstanceId(serviceId);
					final URI agentId = newAgentExecutorId();
					deploymentPlan.addServiceInstance(serviceId, agentId, instanceId);
				}
			}
			else if (newNumberOfInstances < oldNumberOfInstances) {
				for (int i = oldNumberOfInstances - newNumberOfInstances; i > 0; i--) {
					final int index = state.getAndDecrementNextServiceInstanceIndex(serviceId);
					final URI instanceId = newInstanceId(serviceId, index);
					deploymentPlan.removeServiceInstance(instanceId);
				}
			}
		}
		
		final Function<ServiceConfig,URI> getServiceIdFunc = new Function<ServiceConfig,URI>() {

			@Override
			public URI apply(ServiceConfig serviceConfig) {
				return serviceConfig.getServiceId();
			}
		};
		
		Set<URI> plannedServiceIds = Sets.newHashSet(Iterables.transform(state.getDeploymentPlan().getServices(), getServiceIdFunc));
		Set<URI> installedServiceIds = Sets.newHashSet(Iterables.transform(state.getServices(), getServiceIdFunc));
		Set<URI> uninstalledServiceIds = Sets.difference(plannedServiceIds, installedServiceIds);
		
		for (URI uninstalledServiceId : uninstalledServiceIds) {
			state.getDeploymentPlan().removeService(uninstalledServiceId);
		}
		return deploymentPlan;
	}

	private void deploymentPlanUpdateService(ServiceGridDeploymentPlan deploymentPlan, ServiceConfig oldService, ServiceConfig newService) {
		
		final ServiceConfig newServiceClone = StreamUtils.cloneElement(mapper, newService);
		if (oldService == null) {
			deploymentPlan.addService(newServiceClone);
		}
		else if (!StreamUtils.elementEquals(mapper, newService,oldService)) {
			deploymentPlan.replaceService(oldService, newServiceClone);
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
		final int index = state.getAndIncrementNextServiceInstanceIndex(serviceId);
		return newInstanceId(serviceId, index);
	}

	private URI newInstanceId(URI serviceId, final int index) {
		Preconditions.checkArgument(serviceId.toString().endsWith("/"), "service id %s must end with slash", serviceId);
		return newURI(serviceId.toString() + "instances/" + index +"/");
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
	

	private void checkServiceId(final URI serviceId) {
		Preconditions.checkArgument(serviceId.toString().endsWith("/"), "%s must end with /", serviceId);
	}
}
