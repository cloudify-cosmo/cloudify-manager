package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerState;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.RecoverServiceInstanceStateTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;
import org.openspaces.servicegrid.streams.StreamUtils;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

public class MockAgent {

	private final AgentState state;
	private final Map<URI, ServiceInstanceState> instancesState;
	private ObjectMapper mapper = StreamUtils.newJsonObjectMapper();
	
	public MockAgent(AgentState state) {
		this.state = state;
		this.instancesState = Maps.newLinkedHashMap();
	}

	@ImpersonatingTaskConsumer
	public void startServiceInstance(StartServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		Preconditions.checkState(StreamUtils.elementEquals(mapper, instancesState.get(task.getImpersonatedTarget()), instanceState));
		
		instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
		impersonatedStateModifier.updateState(instanceState);
		instancesState.put(task.getImpersonatedTarget(), instanceState);

	}

	@ImpersonatingTaskConsumer
	public void installServiceInstance(InstallServiceInstanceTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		
		Preconditions.checkState(!instancesState.containsKey(task.getImpersonatedTarget()));
		
		ServiceInstanceState instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
		impersonatedStateModifier.updateState(instanceState);
		
		instancesState.put(task.getImpersonatedTarget(), instanceState);
	}

	@ImpersonatingTaskConsumer
	public void recoverServiceInstanceState(RecoverServiceInstanceStateTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		
		URI instanceId = task.getImpersonatedTarget();
		Preconditions.checkArgument(state.getServiceInstanceIds().contains(instanceId), "Wrong impersonating target: " + instanceId);
		ServiceInstanceState instanceState = instancesState.get(instanceId);
		if (instanceState == null) {
			instanceState = new ServiceInstanceState();
			instanceState.setProgress(ServiceInstanceState.Progress.PLANNED);
		}
		
		impersonatedStateModifier.updateState(instanceState);
		
	}
	
	@TaskConsumer
	public void execute(PingAgentTask task) {
		//do nothing
	}
	
	public TaskConsumerState getState() {
		return state;
	}


}
