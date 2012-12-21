package org.openspaces.servicegrid;

import java.net.MalformedURLException;
import java.net.URL;
import java.util.List;
import java.util.UUID;

import org.openspaces.servicegrid.model.service.ServiceOrchestratorState;
import org.openspaces.servicegrid.model.tasks.SetServiceConfigTask;
import org.openspaces.servicegrid.model.tasks.StartMachineTask;
import org.openspaces.servicegrid.model.tasks.Task;

import com.google.common.base.Throwables;
import com.google.common.collect.Lists;

public class ServiceOrchestrator implements Orchestrator<ServiceOrchestratorState> {

	private final ServiceOrchestratorState state;
	private final URL targetExecutorId;
	
	public ServiceOrchestrator(URL targetExecutorId) {
		this.targetExecutorId = targetExecutorId;
		this.state = new ServiceOrchestratorState();
	}

	@Override
	public void execute(Task task) {
		
		if (task instanceof SetServiceConfigTask){
			state.setConfig(((SetServiceConfigTask) task).getServiceConfig());
		}
	}

	@Override
	public List<Task> orchestrate() {
	
		List<Task> newTasks = Lists.newArrayList();
		final StartMachineTask task = new StartMachineTask();
		task.setTarget(targetExecutorId);
		URL instanceId = newInstanceId();
		task.setImpersonatedTarget(instanceId);	
		newTasks.add(task);
		state.addInstanceId(instanceId);
		return newTasks;
	}

	private URL newInstanceId() {
		try {
			return new URL("http://localhost/executors/" + UUID.randomUUID());
		} catch (MalformedURLException e) {
			throw Throwables.propagate(e);
		}
	}

	@Override
	public ServiceOrchestratorState getState() {
		return state;
	}

}
