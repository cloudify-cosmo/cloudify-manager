package org.openspaces.servicegrid.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;
import java.util.UUID;

import org.openspaces.servicegrid.ImpersonatingTaskExecutor;
import org.openspaces.servicegrid.Task;
import org.openspaces.servicegrid.TaskExecutor;
import org.openspaces.servicegrid.TaskExecutorState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PlanAgentTask;
import org.openspaces.servicegrid.service.state.ServiceConfig;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.state.ServiceState;
import org.openspaces.servicegrid.service.tasks.PlanServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.PlanServiceTask;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;
import org.openspaces.servicegrid.time.CurrentTimeProvider;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;

public class ServiceGridPlanner implements TaskExecutor<TaskExecutorState>, ImpersonatingTaskExecutor<TaskExecutorState> {

	private final TaskExecutorState state;
	private final CurrentTimeProvider timeProvider;
	private final StreamProducer<Task> taskProducer;
	private final URI plannerExecutorId;
	private final StreamConsumer<TaskExecutorState> stateReader;
	
	public ServiceGridPlanner(ServiceGridPlannerParameter parameterObject) {
		this.plannerExecutorId = parameterObject.getPlannerExecutorId();
		this.taskProducer = parameterObject.getTaskProducer();
		this.stateReader = parameterObject.getStateReader();
		this.timeProvider = parameterObject.getTimeProvider();
		this.state = new TaskExecutorState();
	}
	
	@Override
	public void execute(Task task) {
		long nowTimestamp = timeProvider.currentTimeMillis();
		
		if (task instanceof PlanTask) {
			Iterable<? extends Task> newTasks = plan((PlanTask)task);
			submitTasks(nowTimestamp, newTasks);
		}
		else {
			Preconditions.checkState(false, "Cannot handle task " + task.getClass());
		}
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
		else {
			Preconditions.checkState(false, "Unkown task " + task.getClass());
		}
	}
	

	private void submitTasks(long nowTimestamp,
			Iterable<? extends Task> newTasks) {
		for (final Task newTask : newTasks) {
			newTask.setSource(plannerExecutorId);
			newTask.setSourceTimestamp(nowTimestamp);
			Preconditions.checkNotNull(newTask.getTarget());
			taskProducer.addElement(newTask.getTarget(), newTask);
		}
	}
	
	private Iterable<Task> plan(PlanTask planTask) {
		
		List<Task> newTasks = Lists.newArrayList();
		
		for (ServiceConfig serviceConfig : planTask.getServices()) {
			URI lastElementId = stateReader.getLastElementId(serviceConfig.getServiceId());
			Preconditions.checkState(lastElementId == null);
			//Service was just added, need to create a state for it
			
			final PlanServiceTask planServiceTask = new PlanServiceTask();
			planServiceTask.setImpersonatedTarget(serviceConfig.getServiceId());
			planServiceTask.setTarget(plannerExecutorId);
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
				planInstanceTask.setTarget(plannerExecutorId);
				addNewTask(newTasks, planInstanceTask);
				
				Preconditions.checkState(stateReader.getLastElementId(agentId) == null);
				final PlanAgentTask planAgentTask = new PlanAgentTask();
				planAgentTask.setImpersonatedTarget(agentId);	
				planAgentTask.setTarget(plannerExecutorId);
				planAgentTask.setServiceInstanceIds(Lists.newArrayList(instanceId));
				addNewTask(newTasks, planAgentTask);
			}
			
			addNewTask(newTasks, planServiceTask);
		}
		
		return newTasks;
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
	public TaskExecutorState getState() {
		return state;
	}

	private static void addNewTask(List<Task> newTasks, final Task task) {
		newTasks.add(task);
	}

}
