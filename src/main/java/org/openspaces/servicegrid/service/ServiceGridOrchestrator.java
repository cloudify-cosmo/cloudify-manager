package org.openspaces.servicegrid.service;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import org.codehaus.jackson.JsonGenerationException;
import org.codehaus.jackson.annotate.JsonIgnore;
import org.codehaus.jackson.map.JsonMappingException;
import org.codehaus.jackson.map.ObjectMapper;
import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.agent.tasks.PlanAgentTask;
import org.openspaces.servicegrid.agent.tasks.DiagnoseAgentNotRespondingTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridOrchestratorState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.OrchestrateServiceTask;
import org.openspaces.servicegrid.service.tasks.PlanServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.beust.jcommander.internal.Sets;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridOrchestrator implements TaskExecutor<ServiceGridOrchestratorState>, ImpersonatingTaskExecutor<ServiceGridOrchestratorState> {

	private static final long ZOMBIE_DETECTION_MILLISECONDS = TimeUnit.SECONDS.toMillis(30);

	private final ServiceGridOrchestratorState state;

	private final ObjectMapper mapper = new ObjectMapper();
	private final StreamConsumer<Task> taskConsumer;
	private final StreamProducer<Task> taskProducer;
	private final URI cloudExecutorId;
	private final URI orchestratorExecutorId;
	private final StreamConsumer<TaskExecutorState> stateReader;
	private final URI agentLifecycleExecutorId;

	private CurrentTimeProvider timeProvider;
	
	public ServiceGridOrchestrator(ServiceOrchestratorParameter parameterObject) {
		this.orchestratorExecutorId = parameterObject.getOrchestratorExecutorId();
		this.agentLifecycleExecutorId = parameterObject.getAgentLifecycleExecutorId();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.cloudExecutorId = parameterObject.getCloudExecutorId();
		this.taskProducer = parameterObject.getTaskProducer();
		this.stateReader = parameterObject.getStateReader();
		this.timeProvider = parameterObject.getTimeProvider();
		this.state = new ServiceGridOrchestratorState();
	}

	@Override
	public void execute(Task task) {
		long nowTimestamp = timeProvider.currentTimeMillis();
		if (task instanceof InstallServiceTask){
			installService((InstallServiceTask) task);
		}
		else if (task instanceof OrchestrateTask) {
			OrchestrateTask orchestrateTask = (OrchestrateTask) task;
			for (int i = 0 ; i < orchestrateTask.getMaxNumberOfOrchestrationSteps(); i++) {
				Iterable<? extends Task> newTasks = orchestrate(nowTimestamp);
				if (Iterables.isEmpty(newTasks)) {
					break;
				}
				for (Task newTask : newTasks) {
					newTask.setSource(orchestratorExecutorId);
					newTask.setSourceTimestamp(nowTimestamp);
					Preconditions.checkNotNull(newTask.getTarget());
					taskProducer.addElement(newTask.getTarget(), newTask);
				}
			}
		}
	}

	private void installService(InstallServiceTask task) {
		boolean installed = isServiceInstalled();
		Preconditions.checkState(!installed);
		ServiceConfig serviceConfig = task.getServiceConfig();
		Preconditions.checkNotNull(serviceConfig);
		fixServiceId(serviceConfig);
		state.addService(serviceConfig);
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

	private boolean isServiceInstalled() {
		boolean installed = false;
		for (final URI oldTaskId : state.getCompletedTasks()) {
			final Task oldTask = taskConsumer.getElement(oldTaskId, Task.class);
			if (oldTask instanceof InstallServiceTask) {
				installed = true;
			}
		}
		return installed;
	}

	private List<Task> orchestrate(long nowTimestamp) {
	
		List<Task> newTasks = Lists.newArrayList();
		
		for (ServiceConfig serviceConfig : state.getServices()) {
			URI lastElementId = stateReader.getLastElementId(serviceConfig.getServiceId());
			//Service was just added, need to create a state for it
			if (lastElementId == null){
				final OrchestrateServiceTask task = new OrchestrateServiceTask();
				task.setImpersonatedTarget(serviceConfig.getServiceId());
				task.setTarget(orchestratorExecutorId);
				addNewTaskIfNotExists(newTasks, task);
			} else {
				ServiceState serviceState = stateReader.getElement(lastElementId, ServiceState.class);
				for (URI instanceId : serviceState.getInstancesIds()) {
					Preconditions.checkNotNull(instanceId);
					URI agentId = serviceState.getAgentIdOfInstance(instanceId);
					Preconditions.checkNotNull(agentId);
					URI agentStreamLastElementId = stateReader.getLastElementId(agentId);
					
					if (agentStreamLastElementId == null) {
						final PlanAgentTask task = new PlanAgentTask();
						task.setImpersonatedTarget(agentId);	
						task.setTarget(orchestratorExecutorId);
						addNewTaskIfNotExists(newTasks, task);
					}
					else {
						AgentState agentState = stateReader.getElement(agentStreamLastElementId, AgentState.class);
						final String agentProgress = agentState.getProgress();
						Preconditions.checkNotNull(agentProgress);
						
						if (agentProgress.equals(AgentState.Progress.PLANNED)){
							final StartMachineTask task = new StartMachineTask();
							task.setImpersonatedTarget(agentId);	
							task.setTarget(cloudExecutorId);
							addNewTaskIfNotExists(newTasks, task);
						}
						else if (agentProgress.equals(AgentState.Progress.MACHINE_STARTED) ||
								 agentProgress.equals(AgentState.Progress.AGENT_NOT_RESPONDING)) {
							final StartAgentTask task = new StartAgentTask();
							task.setImpersonatedTarget(agentId);	
							task.setTarget(agentLifecycleExecutorId);
							task.setIpAddress(agentState.getIpAddress());
							task.setAgentExecutorId(agentId);
							addNewTaskIfNotExists(newTasks, task);
						}
						else if (isAgentNotResponding(agentId, nowTimestamp)) {
							final DiagnoseAgentNotRespondingTask task = new DiagnoseAgentNotRespondingTask();
							task.setImpersonatedTarget(agentId);	
							task.setTarget(agentLifecycleExecutorId);
							task.setIpAddress(agentState.getIpAddress());
							addNewTaskIfNotExists(newTasks, task);
						}
						else {
							URI instanceStreamLastElementId = stateReader.getLastElementId(instanceId);
							if (instanceStreamLastElementId == null){
						
							final PlanServiceInstanceTask task = new PlanServiceInstanceTask();
							task.setServiceId(serviceConfig.getServiceId());
							task.setAgentId(agentId);
							task.setImpersonatedTarget(instanceId);	
							task.setTarget(orchestratorExecutorId);
							addNewTaskIfNotExists(newTasks, task);
							}
							else {
								ServiceInstanceState instanceState = stateReader.getElement(stateReader.getLastElementId(instanceId), ServiceInstanceState.class);
								final String instanceProgress = instanceState.getProgress();
	
								if (instanceProgress.equals(ServiceInstanceState.Progress.PLANNED)) {
									final InstallServiceInstanceTask task = new InstallServiceInstanceTask();
									task.setImpersonatedTarget(instanceId);	
									task.setTarget(agentId);
									addNewTaskIfNotExists(newTasks, task);
								}
								else if (instanceProgress.equals(ServiceInstanceState.Progress.INSTANCE_INSTALLED)) {
									//Ask for start service instance
									final StartServiceInstanceTask task = new StartServiceInstanceTask();
									task.setImpersonatedTarget(instanceId);	
									task.setTarget(agentId);
									addNewTaskIfNotExists(newTasks, task);
								}
								else if (instanceProgress.equals(ServiceInstanceState.Progress.INSTANCE_STARTED)){
									//Do nothing, instance is installed
								}
							}
						}
					}
				}
			}
			
		}
		
		// Ping all agents that are not doing anything
		Set<URI> agentNewTasks = Sets.newHashSet();
		for (Task task : newTasks) {
			agentNewTasks.add(task.getTarget());
		}
		for (URI agentExecutorId : getAgentIds()) {
			if (!agentNewTasks.contains(agentExecutorId)) {
				if (!isAgentExecutingTask(agentExecutorId)) {
					if (getPendingAgentTask(agentExecutorId) == null) {
						final PingAgentTask pingTask = new PingAgentTask();
						pingTask.setTarget(agentExecutorId);
						addNewTask(newTasks, pingTask);
					}
				}
			}
		}
		
		return newTasks;
	}


	@JsonIgnore
	public Iterable<URI> getAgentIds() {
		Set<URI> agentIds = Sets.newLinkedHashSet();
		for (ServiceConfig service : state.getServices()) {
			URI lastElementId = stateReader.getLastElementId(service.getServiceId());
			//Service was just added, need to create a state for it
			if (lastElementId != null) {
				ServiceState serviceState = stateReader.getElement(lastElementId, ServiceState.class);
				for (URI instanceId : serviceState.getInstancesIds()) {
					URI agentId = serviceState.getAgentIdOfInstance(instanceId);
					if (stateReader.getLastElementId(agentId) != null) {
						agentIds.add(agentId);
					}
				}
			}
		}
		return agentIds;
	}

	private boolean isAgentNotResponding(URI agentExecutorId, long nowTimestamp) {
		
		boolean isZombie = false;
		
		if (!isAgentExecutingTask(agentExecutorId)) {
			final URI nextTaskToExecute = getPendingAgentTask(agentExecutorId);
			if (nextTaskToExecute != null) {
				final Task task = taskConsumer.getElement(nextTaskToExecute, Task.class);
				Preconditions.checkState(task.getSource().equals(orchestratorExecutorId), "All agent tasks are assumed to be from this orchestrator");
				if (task instanceof PingAgentTask) {
					final long taskTimestamp = task.getSourceTimestamp();
					final long notRespondingMilliseconds = nowTimestamp - taskTimestamp;
					if ( notRespondingMilliseconds > ZOMBIE_DETECTION_MILLISECONDS ) {
						isZombie = true;
					}
				}
			}
		}
		
		return isZombie;
	}

	/**
	 * Adds a new task only if it has not been added recently.
	 */
	
	private void addNewTaskIfNotExists(
			final List<Task> newTasks,
			final Task newTask) {
		
		final URI agentExecutorId = newTask.getTarget();
		URI existingTaskId = 
			Iterables.find(getExecutingAndPendingAgentTasks(agentExecutorId),
				new Predicate<URI>() {
					@Override
					public boolean apply(URI existingTaskId) {
						Task existingTask = taskConsumer.getElement(existingTaskId, Task.class);
						Preconditions.checkArgument(agentExecutorId.equals(existingTask.getTarget()),"Expected target " + agentExecutorId + " actual target " + existingTask.getTarget());
						return tasksEqualsIgnoreTimestampIgnoreSource(existingTask,newTask);
				}},
				null
			);
		
		if (existingTaskId == null) {
			addNewTask(newTasks, newTask);
		}
	}
	
	private boolean tasksEqualsIgnoreTimestampIgnoreSource(final Task task1, final Task task2) {
		try {
			if (!task1.getClass().equals(task2.getClass())) {
				return false;
			}
			Task task1Clone = mapper.readValue(mapper.writeValueAsBytes(task1), task1.getClass());
			Task task2Clone = mapper.readValue(mapper.writeValueAsBytes(task2), task2.getClass());
			task1Clone.setSourceTimestamp(null);
			task2Clone.setSourceTimestamp(null);
			task1Clone.setSource(null);
			task2Clone.setSource(null);
			String task1CloneString = mapper.writeValueAsString(task1Clone);
			String task2CloneString = mapper.writeValueAsString(task2Clone);
			return task1CloneString.equals(task2CloneString);
		} catch (JsonGenerationException e) {
			throw Throwables.propagate(e);
		} catch (JsonMappingException e) {
			throw Throwables.propagate(e);
		} catch (IOException e) {
			throw Throwables.propagate(e);
		}
	}

	/**
	 * @return the last task for this executor, that its source is this orchestrator
	 *
	private Task getLastTaskFromThis(URI executorId) {
		final URI lastTaskId = this.taskConsumer.getLastElementId(executorId);
		for(URI taskId = lastTaskId; 
			taskId != null; 
			taskId = this.taskConsumer.getPrevElementId(taskId)) {
			
			Task task = taskConsumer.getElement(taskId, Task.class);
			if (orchestratorExecutorId.equals(task.getSource())) {
				return task;
			}
		}
		return null;
	}*/

	private void addNewTask(List<Task> newTasks,
			final Task task) {
		newTasks.add(task);
	}

	private boolean isAgentExecutingTask(URI agentExecutorId) {
		TaskExecutorState agentState = getAgentState(agentExecutorId);
		return agentState != null && !Iterables.isEmpty(agentState.getExecutingTasks());
	}

	private TaskExecutorState getAgentState(URI agentExecutorId) {
		TaskExecutorState agentState = null;
		URI lastAgentStateId = stateReader.getLastElementId(agentExecutorId);
		if (lastAgentStateId != null) {
			agentState = stateReader.getElement(lastAgentStateId, TaskExecutorState.class);
		}
		return agentState;
	}

	private URI getPendingAgentTask(URI agentExecutorId) {
		URI lastCompletedTask = null;
		
		final TaskExecutorState agentState = getAgentState(agentExecutorId);
		if (agentState != null) {
			lastCompletedTask = Iterables.getLast(agentState.getCompletedTasks(),null);
		}
		
		URI nextTaskToExecute = null;
		if (lastCompletedTask == null) {
			nextTaskToExecute = taskConsumer.getFirstElementId(agentExecutorId);
		}
		else {
			nextTaskToExecute = taskConsumer.getNextElementId(lastCompletedTask); 
		}
		
		return nextTaskToExecute;
	}

	private Iterable<URI> getExecutingAndPendingAgentTasks(URI agentExecutorId) {
		 Iterable<URI> tasks = Iterables.concat(getExecutingAgentTasks(agentExecutorId), getPendingAgentTasks(agentExecutorId));
		 return tasks;
	}
	
	private Iterable<URI> getExecutingAgentTasks(URI agentExecutorId) {
		TaskExecutorState agentState = getAgentState(agentExecutorId);
		if (agentState == null) {
			return Lists.newArrayList();
		}
		return agentState.getExecutingTasks();
	}
	
	private Iterable<URI> getPendingAgentTasks(URI agentExecutorId) {

		List<URI> tasks = Lists.newArrayList();
		URI pendingTaskId = getPendingAgentTask(agentExecutorId);
		while (pendingTaskId != null) {
			tasks.add(pendingTaskId);
			pendingTaskId = taskConsumer.getNextElementId(pendingTaskId);
		}
		return tasks;
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
				URI instanceId = newInstanceId(serviceConfig.getServiceId());
				URI agentId = newAgentExecutorId();
				serviceState.addInstanceId(instanceId, agentId);
			}
			impersonatedStateModifier.updateState(serviceState);
		}
		else if (task instanceof PlanServiceInstanceTask) {
			ServiceInstanceState impersonatedServiceInstanceState = new ServiceInstanceState();
			impersonatedServiceInstanceState.setProgress(ServiceInstanceState.Progress.PLANNED);
			//TODO get config from service state or orchestrator state?
			final URI serviceId = ((PlanServiceInstanceTask)task).getServiceId();
			final ServiceConfig serviceConfig = getServiceConfig(serviceId);
			
			impersonatedServiceInstanceState.setDisplayName(serviceConfig.getDisplayName());
			impersonatedServiceInstanceState.setAgentId(((PlanServiceInstanceTask)task).getAgentId());
			impersonatedStateModifier.updateState(impersonatedServiceInstanceState);
		}
		else if (task instanceof PlanAgentTask) {
			AgentState impersonatedAgentState = new AgentState();
			impersonatedAgentState.setProgress(AgentState.Progress.PLANNED);
			impersonatedStateModifier.updateState(impersonatedAgentState);
		}
	}

	private ServiceConfig getServiceConfig(final URI serviceURI) {
		Preconditions.checkNotNull(serviceURI);
		ServiceConfig serviceConfig = Iterables.find(this.state.getServices(), new Predicate<ServiceConfig>() {
			@Override
			public boolean apply(ServiceConfig input){
				return input.getServiceId().equals(serviceURI);
			}
		});
		return serviceConfig;
	}

}
