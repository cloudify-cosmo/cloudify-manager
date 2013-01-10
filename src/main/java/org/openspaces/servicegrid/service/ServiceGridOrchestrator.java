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
import org.openspaces.servicegrid.agent.tasks.RestartNotRespondingAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartAgentTask;
import org.openspaces.servicegrid.agent.tasks.StartMachineTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceGridOrchestratorState;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.InstallServiceTask;
import org.openspaces.servicegrid.service.tasks.PlanServiceTask;
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
		else if (task instanceof PlanTask) {
			Iterable<? extends Task> newTasks = plan((PlanTask)task);
			submitTasks(nowTimestamp, newTasks);
		}
		else if (task instanceof OrchestrateTask) {
			OrchestrateTask orchestrateTask = (OrchestrateTask) task;
			for (int i = 0 ; i < orchestrateTask.getMaxNumberOfOrchestrationSteps(); i++) {
				Iterable<? extends Task> newTasks = orchestrate(nowTimestamp);
				if (Iterables.isEmpty(newTasks)) {
					break;
				}
				submitTasks(nowTimestamp, newTasks);
			}
		}
		else {
			Preconditions.checkState(false, "Cannot handle task " + task.getClass());
		}
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

	private Iterable<Task> plan(PlanTask planTask) {
		
		List<Task> newTasks = Lists.newArrayList();
		
		for (ServiceConfig serviceConfig : state.getServices()) {
			URI lastElementId = stateReader.getLastElementId(serviceConfig.getServiceId());
			Preconditions.checkState(lastElementId == null);
			//Service was just added, need to create a state for it
			
			final PlanServiceTask planServiceTask = new PlanServiceTask();
			planServiceTask.setImpersonatedTarget(serviceConfig.getServiceId());
			planServiceTask.setTarget(orchestratorExecutorId);
			List<URI> serviceInstanceIds = Lists.newArrayList();
			planServiceTask.setServiceInstanceIds(serviceInstanceIds);
			
			for (int i = 0; i < serviceConfig.getNumberOfInstances(); i++) {
				URI instanceId = newInstanceId(serviceConfig.getServiceId());
				URI agentId = newAgentExecutorId();
								
				serviceInstanceIds.add(instanceId);
				
				Preconditions.checkState(stateReader.getLastElementId(instanceId) == null);
				final PlanServiceInstanceTask planInstanceTask = new PlanServiceInstanceTask();
				planInstanceTask.setAgentId(agentId);
				planInstanceTask.setServiceId(serviceConfig.getServiceId());
				planInstanceTask.setImpersonatedTarget(instanceId);	
				planInstanceTask.setTarget(orchestratorExecutorId);
				addNewTaskIfNotExists(newTasks, planInstanceTask);
				
				Preconditions.checkState(stateReader.getLastElementId(agentId) == null);
				final PlanAgentTask planAgentTask = new PlanAgentTask();
				planAgentTask.setImpersonatedTarget(agentId);	
				planAgentTask.setTarget(orchestratorExecutorId);
				planAgentTask.setServiceInstanceIds(Lists.newArrayList(instanceId));
				addNewTaskIfNotExists(newTasks, planAgentTask);
			}
			
			addNewTaskIfNotExists(newTasks, planServiceTask);
		}
		
		return newTasks;
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
			if (lastElementId == null) {
				//no plan yet
				continue;
			}
			ServiceState serviceState = stateReader.getElement(lastElementId, ServiceState.class);
			for (URI instanceId : serviceState.getInstanceIds()) {
				
				URI agentId = getAgentIdOfServiceInstance(instanceId);
				AgentState agentState = stateReader.getElement(stateReader.getLastElementId(agentId), AgentState.class);
				final String agentProgress = agentState.getProgress();
				Preconditions.checkNotNull(agentProgress);
				
				
				ServiceInstanceState instanceState = stateReader.getElement(stateReader.getLastElementId(instanceId), ServiceInstanceState.class);
				final String instanceProgress = instanceState.getProgress();
				Preconditions.checkNotNull(instanceProgress);
				
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
				else if (isAgentNotResponding(agentId, nowTimestamp)) {
					
					final RestartNotRespondingAgentTask task = new RestartNotRespondingAgentTask();
					task.setImpersonatedTarget(agentId);	
					task.setTarget(agentLifecycleExecutorId);
					addNewTaskIfNotExists(newTasks, task);
				}
				else if (instanceProgress.equals(ServiceInstanceState.Progress.PLANNED)) {
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
		
		// Ping all agents that are not doing anything
		Set<URI> agentNewTasks = Sets.newHashSet();
		for (Task task : newTasks) {
			agentNewTasks.add(task.getTarget());
		}
		for (URI agentId : getAgentIds()) {
			if (!agentNewTasks.contains(agentId)) {
				if (!isExecutorExecutingTask(agentId)) {
					if (getPendingExecutorTask(agentId) == null) {
						AgentState agentState = getAgentState(agentId);
						if (agentState.getProgress().equals(AgentState.Progress.AGENT_STARTED)) {
							int numberOfRestarts = agentState.getNumberOfRestarts();
							final PingAgentTask pingTask = new PingAgentTask();
							pingTask.setTarget(agentId);
							pingTask.setNumberOfRestarts(numberOfRestarts);
							addNewTask(newTasks, pingTask);
						}
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

	private boolean isExecutorExecutingTask(URI executorId) {
		TaskExecutorState executorState = getTaskExecutorState(executorId, TaskExecutorState.class);
		return executorState != null && !Iterables.isEmpty(executorState.getExecutingTasks());
	}

	private <T extends TaskExecutorState> T getTaskExecutorState(URI executorId, Class<T> clazz) {
		T executorState = null;
		URI lastAgentStateId = stateReader.getLastElementId(executorId);
		if (lastAgentStateId != null) {
			executorState = stateReader.getElement(lastAgentStateId, clazz);
		}
		return executorState;
	}
	
	private AgentState getAgentState(URI agentExecutorId) {
		return getTaskExecutorState(agentExecutorId, AgentState.class);
	}

	private URI getPendingExecutorTask(URI executorId) {
		URI lastCompletedTask = null;
		
		final TaskExecutorState executorState = getTaskExecutorState(executorId, TaskExecutorState.class);
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
		TaskExecutorState executorState = getTaskExecutorState(executorId, TaskExecutorState.class);
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
		if (task instanceof PlanServiceTask){
			planService((PlanServiceTask) task, impersonatedStateModifier);
		}
		else if (task instanceof PlanServiceInstanceTask) {
			planServiceInstance((PlanServiceInstanceTask) task, impersonatedStateModifier);
		}
		else if (task instanceof PlanAgentTask) {
			planAgent((PlanAgentTask) task, impersonatedStateModifier);
		}
	}

	private void planAgent(PlanAgentTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		AgentState impersonatedAgentState = new AgentState();
		impersonatedAgentState.setProgress(AgentState.Progress.PLANNED);
		impersonatedAgentState.setServiceInstanceIds(task.getServiceInstanceIds());
		impersonatedStateModifier.updateState(impersonatedAgentState);
	}

	private void planServiceInstance(PlanServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		PlanServiceInstanceTask planInstanceTask = (PlanServiceInstanceTask) task;
		ServiceInstanceState instanceState = new ServiceInstanceState();
		instanceState.setProgress(ServiceInstanceState.Progress.PLANNED);
		instanceState.setAgentId(planInstanceTask.getAgentId());
		instanceState.setServiceId(planInstanceTask.getServiceId());
		impersonatedStateModifier.updateState(instanceState);
	}

	private void planService(PlanServiceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		final PlanServiceTask planServiceTask = (PlanServiceTask) task;
		final ServiceState serviceState = new ServiceState();
		serviceState.setServiceConfig(planServiceTask.getServiceConfig());
		serviceState.setInstanceIds(planServiceTask.getServiceInstanceIds());
		impersonatedStateModifier.updateState(serviceState);
	}
}
