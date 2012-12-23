package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.List;
import java.util.UUID;

import org.openspaces.servicegrid.model.service.CreateServiceInstanceExecutorTask;
import org.openspaces.servicegrid.model.service.InstallServiceTask;
import org.openspaces.servicegrid.model.service.ServiceInstanceState;
import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.tasks.StartAgentTask;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;
import org.openspaces.servicegrid.model.tasks.TaskExecutorState;
import org.openspaces.servicegrid.streams.StreamConsumer;
import org.openspaces.servicegrid.streams.StreamProducer;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;

public class ServiceOrchestrator implements TaskExecutor<ServiceOrchestratorState> {

	private final ServiceOrchestratorState state;
	
	private final StreamConsumer<Task> taskConsumer;
	private final StreamProducer<Task> taskProducer;
	private final URL cloudExecutorId;
	private final URL orchestratorExecutorId;
	private final StreamConsumer<TaskExecutorState> stateReader;
	private final URL agentLifecycleExecutorId;
	
	public ServiceOrchestrator(ServiceOrchestratorParameter parameterObject) {
		this.orchestratorExecutorId = parameterObject.getOrchestratorExecutorId();
		this.agentLifecycleExecutorId = parameterObject.getAgentLifecycleExecutorId();
		this.taskConsumer = parameterObject.getTaskConsumer();
		this.cloudExecutorId = parameterObject.getCloudExecutorId();
		this.taskProducer = parameterObject.getTaskProducer();
		this.stateReader = parameterObject.getStateReader();
		this.state = new ServiceOrchestratorState();
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
		state.setDisplayName(task.getDisplayName());
	}

	private boolean isServiceInstalled() {
		boolean installed = false;
		for (final URL oldTaskId : state.getCompletedTaskIds()) {
			final Task oldTask = taskConsumer.getElement(oldTaskId);
			if (oldTask instanceof InstallServiceTask) {
				installed = true;
			}
		}
		return installed;
	}

	private List<Task> orchestrate() {
	
		List<Task> newTasks = Lists.newArrayList();
		
		if (Iterables.isEmpty(state.getInstanceIds())) {
			final StartMachineTask task = new StartMachineTask();
			URL instanceId = newInstanceId();
			task.setImpersonatedTarget(instanceId);	
			task.setTarget(cloudExecutorId);
			newTasks.add(task);
			state.addInstanceId(instanceId);
		}
		else {
			URL instanceId = Iterables.getOnlyElement(state.getInstanceIds());
			ServiceInstanceState instanceState = stateReader.getElement(stateReader.getLastElementId(instanceId));
			Preconditions.checkNotNull(instanceState);
			String progress = instanceState.getProgress();
			
			if (progress.equals(ServiceInstanceState.Progress.STARTING_MACHINE)) {
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
				final CreateServiceInstanceExecutorTask task = new CreateServiceInstanceExecutorTask();
				task.setImpersonatedTarget(instanceId);	
				URL agentExecutorId = instanceState.getAgentExecutorId();
				Preconditions.checkNotNull(agentExecutorId);
				task.setTarget(agentExecutorId);
				newTasks.add(task);
			}
			else {
				throw new IllegalStateException("Unknown service instance state " + progress);
			}
		}
		return newTasks;
	}

	private URL newInstanceId() {
		return newUrl(orchestratorExecutorId.toExternalForm() + "instances/" + UUID.randomUUID());
	}

	private URL newAgentExecutorId() {
		return newUrl(orchestratorExecutorId.toExternalForm() + "../agents/" + UUID.randomUUID());
	}
	
	private URL newUrl(String url) {
		try {
			return new URL(url);
		} catch (final MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}
	
	

	@Override
	public ServiceOrchestratorState getState() {
		return state;
	}

}
