package org.openspaces.servicegrid.service;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.Set;
import java.util.concurrent.TimeUnit;

import org.codehaus.jackson.JsonGenerationException;
import org.codehaus.jackson.annotate.JsonIgnore;
import org.codehaus.jackson.map.JsonMappingException;
import org.codehaus.jackson.map.ObjectMapper;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskProducer;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.agent.tasks.RestartNotRespondingAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridOrchestratorState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.ScaleOutServiceTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;
import org.openspaces.servicegrid.streams.StreamReader;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.beust.jcommander.internal.Sets;
import com.google.common.base.Preconditions;
import com.google.common.base.Predicate;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceGridOrchestrator {

	private static final long ZOMBIE_DETECTION_MILLISECONDS = TimeUnit.SECONDS.toMillis(30);

	private final ServiceGridOrchestratorState state;

	private final ObjectMapper mapper = new ObjectMapper();
	private final StreamReader<Task> taskReader;
	private final URI machineProvisionerId;
	private final URI orchestratorId;
	private final StreamReader<TaskConsumerState> stateReader;

	private CurrentTimeProvider timeProvider;

	private final URI floorPlannerId;
	
	public ServiceGridOrchestrator(ServiceGridOrchestratorParameter parameterObject) {
		this.orchestratorId = parameterObject.getOrchestratorId();
		this.taskReader = parameterObject.getTaskReader();
		this.machineProvisionerId = parameterObject.getMachineProvisionerId();
		this.floorPlannerId = parameterObject.getFloorPlannerId();
		this.stateReader = parameterObject.getStateReader();
		this.timeProvider = parameterObject.getTimeProvider();
		this.state = new ServiceGridOrchestratorState();
	}
	
	@TaskConsumer
	public void scaleOutService(ScaleOutServiceTask task) {
		
		for (ServiceConfig serviceConfig : state.getServices()) {
			if (serviceConfig.getServiceId().equals(task.getServiceId())) {
				int newPlannedNumberOfInstances = task.getPlannedNumberOfInstances();
				if (serviceConfig.getPlannedNumberOfInstances() != newPlannedNumberOfInstances) {
					serviceConfig.setPlannedNumberOfInstances(newPlannedNumberOfInstances);
					state.setFloorPlanningRequired(true);
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
		state.setFloorPlanningRequired(true);
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

	@TaskProducer
	public Iterable<Task> orchestrate(OrchestrateTask task) {
	
		long nowTimestamp = timeProvider.currentTimeMillis();
		List<Task> newTasks = Lists.newArrayList();
		
		if (state.FloorPlanningRequired()) {
			orchestrateFloorPlanning(newTasks);
			state.setFloorPlanningRequired(false);
		}
		else {
			
			final Iterable<URI> healthyAgents = orchestrateAgents(newTasks, nowTimestamp);
		
			orchestrateService(newTasks, healthyAgents);
			
			pingIdleAgents(newTasks);
		}
		
		return newTasks;
	}

	private void orchestrateFloorPlanning(List<Task> newTasks) {
		final FloorPlanTask planTask = new FloorPlanTask();
		planTask.setServices(state.getServices());
		planTask.setTarget(floorPlannerId);
		addNewTask(newTasks, planTask);
	}

	private void orchestrateService(
			List<Task> newTasks,
			final Iterable<URI> healthyAgents) {
		
		for (final ServiceConfig serviceConfig : state.getServices()) {
			
			final ServiceState serviceState = getServiceState(serviceConfig.getServiceId());
			if (serviceState!= null) {
				for (final URI instanceId : serviceState.getInstanceIds()) {
					
					final URI agentId = getAgentIdOfServiceInstance(instanceId);
					if (!Iterables.contains(healthyAgents,agentId)) {
						//no agent yet
						continue;
					}
					
					orchestrateServiceInstance(newTasks, instanceId, agentId);
				}
			}
		}
	}

	private ServiceState getServiceState(URI serviceId) {
		ServiceState serviceState = null;
		final URI lastElementId = stateReader.getLastElementId(serviceId);
		if (lastElementId != null) {
			serviceState = stateReader.getElement(lastElementId, ServiceState.class);
		}
		return serviceState;
	}

	/**
	 * Ping all agents that are not doing anything
	 */
	private void pingIdleAgents(List<Task> newTasks) {
		
		final Set<URI> agentNewTasks = Sets.newHashSet();
		for (final Task task : newTasks) {
			agentNewTasks.add(task.getTarget());
		}
		for (final URI agentId : getAgentIds()) {
			if (!agentNewTasks.contains(agentId) &&
				!isExecutingTask(agentId) &&
				getNextTaskToConsume(agentId) == null) {
					
				final AgentState agentState = getAgentState(agentId);
				if (agentState.getProgress().equals(AgentState.Progress.AGENT_STARTED)) {
					final int numberOfRestarts = agentState.getNumberOfRestarts();
					final PingAgentTask pingTask = new PingAgentTask();
					pingTask.setTarget(agentId);
					pingTask.setNumberOfRestarts(numberOfRestarts);
					addNewTask(newTasks, pingTask);
				}
			}
		}
	}

	private void orchestrateServiceInstance(List<Task> newTasks, URI instanceId, URI agentId) {
		ServiceInstanceState instanceState = stateReader.getElement(stateReader.getLastElementId(instanceId), ServiceInstanceState.class);
		final String instanceProgress = instanceState.getProgress();
		Preconditions.checkNotNull(instanceProgress);
		
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
		else {
			Preconditions.checkState(false, "Unknown service instance progress " + instanceProgress);
		}
	}

	private Iterable<URI> orchestrateAgents(List<Task> newTasks, long nowTimestamp) {
		Set<URI> healthyAgents = Sets.newHashSet();
		for (URI agentId : getAgentIds()) {
			
			AgentState agentState = stateReader.getElement(stateReader.getLastElementId(agentId), AgentState.class);
			final String agentProgress = agentState.getProgress();
			Preconditions.checkNotNull(agentProgress);
			
			if (agentProgress.equals(AgentState.Progress.PLANNED)){
				final StartMachineTask task = new StartMachineTask();
				task.setImpersonatedTarget(agentId);	
				task.setTarget(machineProvisionerId);
				addNewTaskIfNotExists(newTasks, task);
			}
			else if (agentProgress.equals(AgentState.Progress.MACHINE_STARTED)) {
				final StartAgentTask task = new StartAgentTask();
				task.setImpersonatedTarget(agentId);	
				task.setTarget(machineProvisionerId);
				task.setIpAddress(agentState.getIpAddress());
				addNewTaskIfNotExists(newTasks, task);
			}
			else if (agentProgress.equals(AgentState.Progress.AGENT_STARTED)) {
				
				if (isAgentNotResponding(agentId, nowTimestamp)) {
					
					final RestartNotRespondingAgentTask task = new RestartNotRespondingAgentTask();
					task.setImpersonatedTarget(agentId);	
					task.setTarget(machineProvisionerId);
					addNewTaskIfNotExists(newTasks, task);
				}
				else {
					healthyAgents.add(agentId);
				}
			}
			else {
				Preconditions.checkState(false, "Unrecognized agent state " + agentProgress);
			}
		}
		return Iterables.unmodifiableIterable(healthyAgents);
	}


	@JsonIgnore
	public Iterable<URI> getAgentIds() {
		Set<URI> agentIds = Sets.newLinkedHashSet();
		for (ServiceConfig service : state.getServices()) {
			ServiceState serviceState = ServiceUtils.getLastState(stateReader, service.getServiceId(), ServiceState.class);
			if (serviceState != null) {
				for (URI instanceId : serviceState.getInstanceIds()) {
					final URI agentId = getAgentIdOfServiceInstance(instanceId);
					if (stateReader.getLastElementId(agentId) != null) {
						agentIds.add(agentId);
					}
				}
			}
		}
		return agentIds;
	}

	private URI getAgentIdOfServiceInstance(URI instanceId) {
		final ServiceInstanceState serviceInstanceState = stateReader.getElement(stateReader.getLastElementId(instanceId), ServiceInstanceState.class);
		return serviceInstanceState.getAgentId();
	}

	private boolean isAgentNotResponding(URI agentId, long nowTimestamp) {
		
		boolean isZombie = false;
		
		if (!isExecutingTask(agentId)) {
			final URI nextTaskToConsume = getNextTaskToConsume(agentId);
			if (nextTaskToConsume != null) {
				final Task task = taskReader.getElement(nextTaskToConsume, Task.class);
				Preconditions.checkState(task.getSource().equals(orchestratorId), "All agent tasks are assumed to be from this orchestrator");
				if (task instanceof PingAgentTask) {
					PingAgentTask pingAgentTask = (PingAgentTask) task;
					AgentState agentState = getAgentState(agentId);
					if (agentState.getNumberOfRestarts() == pingAgentTask.getNumberOfRestarts()) {
						final long taskTimestamp = task.getSourceTimestamp();
						final long notRespondingMilliseconds = nowTimestamp - taskTimestamp;
						if ( notRespondingMilliseconds > ZOMBIE_DETECTION_MILLISECONDS ) {
							isZombie = true;
						}
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
		
		if (getExistingTaskId(newTask) == null) {
			addNewTask(newTasks, newTask);
		}
	}

	private URI getExistingTaskId(final Task newTask) {
		final URI agentId = newTask.getTarget();
		final URI existingTaskId = 
			Iterables.find(getExecutingAndPendingAgentTasks(agentId),
				new Predicate<URI>() {
					@Override
					public boolean apply(final URI existingTaskId) {
						final Task existingTask = taskReader.getElement(existingTaskId, Task.class);
						Preconditions.checkArgument(agentId.equals(existingTask.getTarget()),"Expected target " + agentId + " actual target " + existingTask.getTarget());
						return tasksEqualsIgnoreTimestampIgnoreSource(existingTask,newTask);
				}},
				null
			);
		return existingTaskId;
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

	private static void addNewTask(List<Task> newTasks, final Task task) {
		newTasks.add(task);
	}

	private boolean isExecutingTask(URI taskConsumerId) {
		TaskConsumerState taskConsumerState = ServiceUtils.getLastState(stateReader, taskConsumerId, TaskConsumerState.class);
		return taskConsumerState != null && !Iterables.isEmpty(taskConsumerState.getExecutingTasks());
	}

	private AgentState getAgentState(URI agentId) {
		return ServiceUtils.getLastState(stateReader, agentId, AgentState.class);
	}

	private URI getNextTaskToConsume(URI executorId) {
		URI lastTask = null;
		
		final TaskConsumerState state = ServiceUtils.getLastState(stateReader, executorId, TaskConsumerState.class);
		if (state != null) {
			lastTask = Iterables.getLast(state.getCompletedTasks(),null);
		}
		
		URI nextTask = null;
		if (lastTask == null) {
			nextTask = taskReader.getFirstElementId(executorId);
		}
		else {
			nextTask = taskReader.getNextElementId(lastTask); 
		}
		
		return nextTask;
	}

	private Iterable<URI> getExecutingAndPendingAgentTasks(URI executorId) {
		 Iterable<URI> tasks = Iterables.concat(getExecutingTasks(executorId), getNextTasksToConsume(executorId));
		 return tasks;
	}
	
	private Iterable<URI> getExecutingTasks(URI executorId) {
		TaskConsumerState executorState = ServiceUtils.getLastState(stateReader, executorId, TaskConsumerState.class);
		if (executorState == null) {
			return Lists.newArrayList();
		}
		return executorState.getExecutingTasks();
	}
	
	private Iterable<URI> getNextTasksToConsume(URI id) {

		List<URI> tasks = Lists.newArrayList();
		URI pendingTaskId = getNextTaskToConsume(id);
		while (pendingTaskId != null) {
			tasks.add(pendingTaskId);
			pendingTaskId = taskReader.getNextElementId(pendingTaskId);
		}
		return tasks;
	}
		
	public ServiceGridOrchestratorState getState() {
		return state;
	}
}
