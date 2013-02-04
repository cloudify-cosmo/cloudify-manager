package org.openspaces.servicegrid.mock;

import java.net.URI;
import java.util.Map;

import org.openspaces.servicegrid.ImpersonatingTaskConsumer;
import org.openspaces.servicegrid.TaskConsumer;
import org.openspaces.servicegrid.TaskConsumerStateHolder;
import org.openspaces.servicegrid.TaskConsumerStateModifier;
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
			TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		ServiceInstanceState instanceState = impersonatedStateModifier.get();
		
		instanceState.setProgress(ServiceInstanceState.Progress.STARTING_INSTANCE);
		impersonatedStateModifier.put(instanceState);
		
		// the code that actually starts the instance goes here
		
		instanceState = impersonatedStateModifier.get();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STARTED);
		impersonatedStateModifier.put(instanceState);
		instancesState.put(task.getStateId(), instanceState);

	}

	@ImpersonatingTaskConsumer
	public void stopServiceInstance(StopServiceInstanceTask task, 
			TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		final URI instanceId = task.getStateId();
		final ServiceInstanceState instanceState = impersonatedStateModifier.get();
		instanceState.setProgress(ServiceInstanceState.Progress.STOPPING_INSTANCE);
		impersonatedStateModifier.put(instanceState);
		
		// the code that actually stops the instance goes here
		instancesState.remove(instanceId);
		
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_STOPPED);
		impersonatedStateModifier.put(instanceState);
		
		state.removeServiceInstanceId(instanceId);
	}
	
	@ImpersonatingTaskConsumer
	public void installServiceInstance(InstallServiceInstanceTask task,
			TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		Preconditions.checkState(!instancesState.containsKey(task.getStateId()));
		
		ServiceInstanceState instanceState = impersonatedStateModifier.get();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTALLING_INSTANCE);
		impersonatedStateModifier.put(instanceState);
		instanceState = impersonatedStateModifier.get();
		instanceState.setProgress(ServiceInstanceState.Progress.INSTANCE_INSTALLED);
		impersonatedStateModifier.put(instanceState);
		
		instancesState.put(task.getStateId(), instanceState);
	}

	@ImpersonatingTaskConsumer
	public void recoverServiceInstanceState(RecoverServiceInstanceStateTask task,
			TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		URI instanceId = task.getStateId();
		URI agentId = task.getConsumerId();
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
		impersonatedStateModifier.put(instanceState);
	}
	
	@ImpersonatingTaskConsumer
	public void injectPropertyToInstance(SetInstancePropertyTask task, TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		final URI instanceId = task.getStateId();
		Preconditions.checkArgument(instancesState.containsKey(instanceId), "Unknown instance %s", instanceId);
		ServiceInstanceState instanceState = instancesState.get(instanceId);
		instanceState.setProperty(task.getPropertyName(), task.getPropertyValue());
		impersonatedStateModifier.put(instanceState);
	}
	
	@TaskConsumer(noHistory = true)
	public void ping(PingAgentTask task) {
		state.setLastPingSourceTimestamp(task.getProducerTimestamp());
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
