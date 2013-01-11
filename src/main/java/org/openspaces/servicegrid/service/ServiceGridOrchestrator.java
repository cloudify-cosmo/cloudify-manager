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
import org.openspaces.servicegrid.TaskExecutorState;
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
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
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
	private final StreamConsumer<Task> taskConsumer;
	private final StreamProducer<Task> taskProducer;
	private final URI cloudExecutorId;
	private final URI orchestratorExecutorId;
	private final StreamConsumer<TaskExecutorState> stateReader;
	private final URI agentLifecycleExecutorId;

	private CurrentTimeProvider timeProvider;

	private final URI floorPlannerExecutorId;
	
	public ServiceGridOrchestrator(ServiceGridOrchestratorParameter parameterObject) {
		this.orchestratorExecutorId = parameterObject.getOrchestratorExecutorId();
		this.agentLifecycleExecutorId = parameterObject.getAgentLifecycleExecutorId();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.cloudExecutorId = parameterObject.getCloudExecutorId();
		this.floorPlannerExecutorId = parameterObject.getPlannerExecutorId();
		this.taskProducer = parameterObject.getTaskProducer();
		this.stateReader = parameterObject.getStateReader();
		this.timeProvider = parameterObject.getTimeProvider();
		this.state = new ServiceGridOrchestratorState();
	}

	public void execute(final OrchestrateTask task) {
		long nowTimestamp = timeProvider.currentTimeMillis();
		for (int i = 0 ; i < task.getMaxNumberOfOrchestrationSteps(); i++) {
			final Iterable<? extends Task> newTasks = orchestrate(nowTimestamp);
			if (Iterables.isEmpty(newTasks)) {
				break;
			}
			submitTasks(nowTimestamp, newTasks);
		}
	}

	public void execute(ScaleOutServiceTask task) {
		
		for (ServiceConfig serviceConfig : state.getServices()) {
			if (serviceConfig.getServiceId().equals(task.getServiceId())) {
				int newPlannedNumberOfInstances = task.getPlannedNumberOfInstances();
				if (serviceConfig.getPlannedNumberOfInstances() != newPlannedNumberOfInstances) {
					serviceConfig.setPlannedNumberOfInstances(newPlannedNumberOfInstances);
					state.setFloorPlanned(false);
					return;
				}
			}
		}
		Preconditions.checkArgument(false,"Cannot find service %s", task.getServiceId());
	}

	private void submitTasks(long nowTimestamp,
			Iterable<? extends Task> newTasks) {
		for (final Task newTask : newTasks) {
			newTask.setSource(orchestratorExecutorId);
			newTask.setSourceTimestamp(nowTimestamp);
			Preconditions.checkNotNull(newTask.getTarget());
			taskProducer.addElement(newTask.getTarget(), newTask);
		}
	}

	public void execute(InstallServiceTask task) {
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
		
		floorPlanning(newTasks);
		
		final Iterable<URI> healthyAgents = orchestrateAgents(newTasks, nowTimestamp);
		
		orchestrateService(newTasks, healthyAgents);
		
		pingIdleAgents(newTasks);
		
		return newTasks;
	}

	private void floorPlanning(List<Task> newTasks) {
		if (!state.isFloorPlanned()) {
			final FloorPlanTask planTask = new FloorPlanTask();
			planTask.setServices(state.getServices());
			planTask.setTarget(floorPlannerExecutorId);
			addNewTask(newTasks, planTask);
			state.setFloorPlanned(true);
		}
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
				!isExecutorExecutingTask(agentId) &&
				getPendingExecutorTask(agentId) == null) {
					
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
				task.setTarget(cloudExecutorId);
				addNewTaskIfNotExists(newTasks, task);
			}
			else if (agentProgress.equals(AgentState.Progress.MACHINE_STARTED)) {
				final StartAgentTask task = new StartAgentTask();
				task.setImpersonatedTarget(agentId);	
				task.setTarget(agentLifecycleExecutorId);
				task.setIpAddress(agentState.getIpAddress());
				addNewTaskIfNotExists(newTasks, task);
			}
			else if (agentProgress.equals(AgentState.Progress.AGENT_STARTED)) {
				
				if (isAgentNotResponding(agentId, nowTimestamp)) {
					
					final RestartNotRespondingAgentTask task = new RestartNotRespondingAgentTask();
					task.setImpersonatedTarget(agentId);	
					task.setTarget(agentLifecycleExecutorId);
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

	private boolean isAgentNotResponding(URI agentExecutorId, long nowTimestamp) {
		
		boolean isZombie = false;
		
		if (!isExecutorExecutingTask(agentExecutorId)) {
			final URI nextTaskToExecute = getPendingExecutorTask(agentExecutorId);
			if (nextTaskToExecute != null) {
				final Task task = taskConsumer.getElement(nextTaskToExecute, Task.class);
				Preconditions.checkState(task.getSource().equals(orchestratorExecutorId), "All agent tasks are assumed to be from this orchestrator");
				if (task instanceof PingAgentTask) {
					PingAgentTask pingAgentTask = (PingAgentTask) task;
					AgentState agentState = getAgentState(agentExecutorId);
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

	private static void addNewTask(List<Task> newTasks, final Task task) {
		newTasks.add(task);
	}

	private boolean isExecutorExecutingTask(URI executorId) {
		TaskExecutorState executorState = ServiceUtils.getLastState(stateReader, executorId, TaskExecutorState.class);
		return executorState != null && !Iterables.isEmpty(executorState.getExecutingTasks());
	}

	private AgentState getAgentState(URI agentId) {
		return ServiceUtils.getLastState(stateReader, agentId, AgentState.class);
	}

	private URI getPendingExecutorTask(URI executorId) {
		URI lastCompletedTask = null;
		
		final TaskExecutorState executorState = ServiceUtils.getLastState(stateReader, executorId, TaskExecutorState.class);
		if (executorState != null) {
			lastCompletedTask = Iterables.getLast(executorState.getCompletedTasks(),null);
		}
		
		URI nextTaskToExecute = null;
		if (lastCompletedTask == null) {
			nextTaskToExecute = taskConsumer.getFirstElementId(executorId);
		}
		else {
			nextTaskToExecute = taskConsumer.getNextElementId(lastCompletedTask); 
		}
		
		return nextTaskToExecute;
	}

	private Iterable<URI> getExecutingAndPendingAgentTasks(URI executorId) {
		 Iterable<URI> tasks = Iterables.concat(getExecutingTasks(executorId), getPendingExecutorTasks(executorId));
		 return tasks;
	}
	
	private Iterable<URI> getExecutingTasks(URI executorId) {
		TaskExecutorState executorState = ServiceUtils.getLastState(stateReader, executorId, TaskExecutorState.class);
		if (executorState == null) {
			return Lists.newArrayList();
		}
		return executorState.getExecutingTasks();
	}
	
	private Iterable<URI> getPendingExecutorTasks(URI executorId) {

		List<URI> tasks = Lists.newArrayList();
		URI pendingTaskId = getPendingExecutorTask(executorId);
		while (pendingTaskId != null) {
			tasks.add(pendingTaskId);
			pendingTaskId = taskConsumer.getNextElementId(pendingTaskId);
		}
		return tasks;
	}
		
	public ServiceGridOrchestratorState getState() {
		return state;
	}
}
