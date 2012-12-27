package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.List;
import java.util.UUID;

import org.openspaces.servicegrid.model.service.InstallServiceInstanceTask;
import org.openspaces.servicegrid.model.service.InstallServiceTask;
import org.openspaces.servicegrid.model.service.OrchestrateServiceInstanceTask;
import org.openspaces.servicegrid.model.service.OrchestrateServiceTask;
import org.openspaces.servicegrid.model.service.ServiceGridOrchestratorState;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceState;
import org.openspaces.servicegrid.model.service.StartServiceInstanceTask;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridOrchestrator implements TaskExecutor<ServiceGridOrchestratorState>, ImpersonatingTaskExecutor<ServiceGridOrchestratorState> {

	private final ServiceGridOrchestratorState state;
	
	private final StreamConsumer<Task> taskConsumer;
	private final StreamProducer<Task> taskProducer;
	private final URL cloudExecutorId;
	private final URL orchestratorExecutorId;
	private final StreamConsumer<TaskExecutorState> stateReader;
	private final URL agentLifecycleExecutorId;
	
	public ServiceGridOrchestrator(ServiceOrchestratorParameter parameterObject) {
		this.orchestratorExecutorId = parameterObject.getOrchestratorExecutorId();
		this.agentLifecycleExecutorId = parameterObject.getAgentLifecycleExecutorId();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.cloudExecutorId = parameterObject.getCloudExecutorId();
		this.taskProducer = parameterObject.getTaskProducer();
		this.stateReader = parameterObject.getStateReader();
		this.state = new ServiceGridOrchestratorState();
	}

	@Override
	public void execute(Task task) {
		
		if (task instanceof InstallServiceTask){
			installService((InstallServiceTask) task);
		}
		else if (task instanceof OrchestrateTask) {
			Iterable<? extends Task> newTasks = orchestrate();
			for (Task newTask : newTasks) {
				newTask.setSource(orchestratorExecutorId);
				Preconditions.checkNotNull(newTask.getTarget());
				taskProducer.addElement(newTask.getTarget(), newTask);
			}
		}
	}

	private void installService(InstallServiceTask task) {
		boolean installed = isServiceInstalled();
		Preconditions.checkState(!installed);
		ServiceConfig serviceConfig = task.getServiceConfig();
		Preconditions.checkNotNull(serviceConfig);
		state.addService(serviceConfig);
	}

	private boolean isServiceInstalled() {
		boolean installed = false;
		for (final URL oldTaskId : state.getCompletedTaskIds()) {
			final Task oldTask = taskConsumer.getElement(oldTaskId, Task.class);
			if (oldTask instanceof InstallServiceTask) {
				installed = true;
			}
		}
		return installed;
	}

	private List<Task> orchestrate() {
	
		List<Task> newTasks = Lists.newArrayList();
		for (ServiceConfig serviceConfig : state.getServices()) {
			URL lastElementId = stateReader.getLastElementId(serviceConfig.getServiceUrl());
			//Service was just added, need to create a state for it
			if (lastElementId == null){
				final OrchestrateServiceTask task = new OrchestrateServiceTask();
				task.setImpersonatedTarget(serviceConfig.getServiceUrl());
				task.setTarget(orchestratorExecutorId);
				newTasks.add(task);
			} else {
				ServiceState serviceState = stateReader.getElement(lastElementId, ServiceState.class);
				for (URL instanceId : serviceState.getInstancesIds()) {
					URL instanceStreamLastElementId = stateReader.getLastElementId(instanceId);
					if (instanceStreamLastElementId == null){
						final OrchestrateServiceInstanceTask task = new OrchestrateServiceInstanceTask();
						task.setServiceUrl(serviceConfig.getServiceUrl());
						task.setImpersonatedTarget(instanceId);	
						task.setTarget(orchestratorExecutorId);
						newTasks.add(task);
					}
					else {
						ServiceInstanceState instanceState = stateReader.getElement(stateReader.getLastElementId(instanceId), ServiceInstanceState.class);
						String progress = instanceState.getProgress();
						if (progress.equals(ServiceInstanceState.Progress.ORCHESTRATING)){
							final StartMachineTask task = new StartMachineTask();
							task.setImpersonatedTarget(instanceId);	
							task.setTarget(cloudExecutorId);
							newTasks.add(task);
						}
						else if (progress.equals(ServiceInstanceState.Progress.STARTING_MACHINE)) {
							//Do nothing, orchestrator needs to wait for the machine to be started
						}
						else if (progress.equals(ServiceInstanceState.Progress.MACHINE_STARTED)) {
							final StartAgentTask task = new StartAgentTask();
							task.setImpersonatedTarget(instanceId);	
							task.setTarget(agentLifecycleExecutorId);
							task.setIpAddress(instanceState.getIpAddress());
							task.setAgentExecutorId(newAgentExecutorId());
							newTasks.add(task);
						}
						else if (progress.equals(ServiceInstanceState.Progress.AGENT_STARTED)) {
							final InstallServiceInstanceTask task = new InstallServiceInstanceTask();
							task.setImpersonatedTarget(instanceId);	
							URL agentExecutorId = instanceState.getAgentExecutorId();
							Preconditions.checkNotNull(agentExecutorId);
							task.setTarget(agentExecutorId);
							newTasks.add(task);
						}
						else if (progress.equals(ServiceInstanceState.Progress.INSTALLING_INSTANCE)) {
							//Do nothing, orchestrator needs to wait for the instance to be installed
						}
						else if (progress.equals(ServiceInstanceState.Progress.INSTANCE_INSTALLED)) {
							//Ask for start service instance
							final StartServiceInstanceTask task = new StartServiceInstanceTask();
							task.setImpersonatedTarget(instanceId);	
							URL agentExecutorId = instanceState.getAgentExecutorId();
							Preconditions.checkNotNull(agentExecutorId);
							task.setTarget(agentExecutorId);
							newTasks.add(task);
						}
						else if (progress.equals(ServiceInstanceState.Progress.STARTING_INSTANCE)){
							//Do nothing, wait for instance to start
						}
						else if (progress.equals(ServiceInstanceState.Progress.INSTANCE_STARTED)){
							//Do nothing, instance is installed
						}
					}
				}
			}
			
		}
		return newTasks;
	}

	private URL newInstanceId() {
		return newUrl(orchestratorExecutorId.toExternalForm() + "instances/" + UUID.randomUUID());
	}

	private URL newAgentExecutorId() {
		return newUrl("http://localhost/agent/" + UUID.randomUUID());
	}
	
	private URL newUrl(String url) {
		try {
			return new URL(url);
		} catch (final MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}
	
	

	@Override
	public ServiceGridOrchestratorState getState() {
		return state;
	}

	@Override
	public void execute(Task task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		if (task instanceof OrchestrateServiceTask){
			final ServiceState serviceState = new ServiceState();
			final ServiceConfig serviceConfig = getServiceConfig(task.getImpersonatedTarget());
			serviceState.setServiceConfig(serviceConfig);
			
			for (int i = 0; i < serviceConfig.getNumberOfInstances(); i++) {
				URL instanceId = newInstanceId();
				serviceState.addInstanceId(instanceId);
			}
			impersonatedStateModifier.updateState(serviceState);
		}
		else if (task instanceof OrchestrateServiceInstanceTask){
			ServiceInstanceState impersonatedServiceInstanceState = new ServiceInstanceState();
			impersonatedServiceInstanceState.setProgress(ServiceInstanceState.Progress.ORCHESTRATING);
			//TODO get config from service state or orchestrator state?
			final URL serviceUrl = ((OrchestrateServiceInstanceTask)task).getServiceUrl();
			final ServiceConfig serviceConfig = getServiceConfig(serviceUrl);
			
			impersonatedServiceInstanceState.setDisplayName(serviceConfig.getDisplayName());			
			impersonatedStateModifier.updateState(impersonatedServiceInstanceState);
		}
		
	}

	private ServiceConfig getServiceConfig(final URL serviceUrl) {
		Preconditions.checkNotNull(serviceUrl);
		ServiceConfig serviceConfig = Iterables.find(this.state.getServices(), new Predicate<ServiceConfig>() {
			@Override
			public boolean apply(ServiceConfig input){
				return input.getServiceUrl().equals(serviceUrl);
			}
		});
		return serviceConfig;
	}

}
