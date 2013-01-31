package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskExecutorStateModifier;
import org.openspaces.servicegrid.agent.state.AgentState;
import org.openspaces.servicegrid.agent.tasks.PingAgentTask;
import org.openspaces.servicegrid.service.state.ServiceInstanceState;
import org.openspaces.servicegrid.service.tasks.InstallServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.MarkAgentAsStoppingTask;
import org.openspaces.servicegrid.service.tasks.RecoverServiceInstanceStateTask;
import org.openspaces.servicegrid.service.tasks.SetInstancePropertyTask;
import org.openspaces.servicegrid.service.tasks.StartServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.StopServiceInstanceTask;

import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;

public class MockAgent {

	private final AgentState state;
	private final Map<URI, ServiceInstanceState> instancesState;
	
	public MockAgent(AgentState state) {
		this.state = state;
		this.instancesState = Maps.newLinkedHashMap();
	}

	@ImpersonatingTaskConsumer
	public void startServiceInstance(StartServiceInstanceTask task,
			TaskExecutorStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		ServiceInstanceState instanceState = impersonatedStateModifier.getState(ServiceInstanceState.class);
		
		instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		
		// the code that actually starts the instance goes here
		
		instanceState = impersonatedStateModifier.getState(ServiceInstanceState.class);
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
		impersonatedStateModifier.updateState(instanceState);
		instancesState.put(task.getImpersonatedTarget(), instanceState);

	}

	@ImpersonatingTaskConsumer
	public void stopServiceInstance(StopServiceInstanceTask task, 
			TaskExecutorStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		final URI instanceId = task.getImpersonatedTarget();
		final ServiceInstanceState instanceState = impersonatedStateModifier.getState(ServiceInstanceState.class);
		instanceState.setProgress(ServiceInstanceState.Progress.STOPPING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		
		// the code that actually stops the instance goes here
		instancesState.remove(instanceId);
		
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STOPPED);
		impersonatedStateModifier.updateState(instanceState);
		
		state.removeServiceInstanceId(instanceId);
	}
	
	@ImpersonatingTaskConsumer
	public void installServiceInstance(InstallServiceInstanceTask task,
			TaskExecutorStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		Preconditions.checkState(!instancesState.containsKey(task.getImpersonatedTarget()));
		
		ServiceInstanceState instanceState = impersonatedStateModifier.getState(ServiceInstanceState.class);
		instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
		impersonatedStateModifier.updateState(instanceState);
		instanceState = impersonatedStateModifier.getState(ServiceInstanceState.class);
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
		impersonatedStateModifier.updateState(instanceState);
		
		instancesState.put(task.getImpersonatedTarget(), instanceState);
	}

	@ImpersonatingTaskConsumer
	public void recoverServiceInstanceState(RecoverServiceInstanceStateTask task,
			TaskExecutorStateModifier impersonatedStateModifier) {
		
		URI instanceId = task.getImpersonatedTarget();
		URI agentId = task.getTarget();
		URI serviceId = task.getServiceId();
		Preconditions.checkArgument(state.getServiceInstanceIds().contains(instanceId), "Wrong impersonating target: " + instanceId);
		ServiceInstanceState instanceState = instancesState.get(instanceId);
		if (instanceState == null) {
			instanceState = new ServiceInstanceState();
			instanceState.setProgress(ServiceInstanceState.Progress.PLANNED);
			instanceState.setAgentId(agentId);
			instanceState.setServiceId(serviceId);
		}
		else {
			Preconditions.checkState(instanceState.getAgentId().equals(agentId));
			Preconditions.checkState(instanceState.getServiceId().equals(serviceId));
		}
		impersonatedStateModifier.updateState(instanceState);
	}
	
	@ImpersonatingTaskConsumer
	public void injectPropertyToInstance(SetInstancePropertyTask task, TaskExecutorStateModifier impersonatedStateModifier) {
		final URI instanceId = task.getImpersonatedTarget();
		Preconditions.checkArgument(instancesState.containsKey(instanceId), "Unknown instance %s", instanceId);
		ServiceInstanceState instanceState = instancesState.get(instanceId);
		instanceState.setProperty(task.getPropertyName(), task.getPropertyValue());
		impersonatedStateModifier.updateState(instanceState);
	}
	
	@TaskConsumer
	public void ping(PingAgentTask task) {
		state.setLastPingSourceTimestamp(task.getSourceTimestamp());
	}
	
	@TaskConsumer
	public void markAgentAsStopping(MarkAgentAsStoppingTask task) {
		Preconditions.checkState(state.getProgress().equals(AgentState.Progress.AGENT_STARTED));
		state.setProgress(AgentState.Progress.STOPPING_AGENT);
	}
	
	@TaskConsumerStateHolder
	public AgentState getState() {
		return state;
	}


}
