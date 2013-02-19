/*******************************************************************************
 * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *       http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ******************************************************************************/
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
import org.openspaces.servicegrid.service.tasks.MarkAgentAsStoppingTask;
import org.openspaces.servicegrid.service.tasks.RecoverServiceInstanceStateTask;
import org.openspaces.servicegrid.service.tasks.RemoveServiceInstanceFromAgentTask;
import org.openspaces.servicegrid.service.tasks.ServiceInstanceTask;
import org.openspaces.servicegrid.service.tasks.SetInstancePropertyTask;

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
	public void serviceInstanceLifecycle(ServiceInstanceTask task,
			TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
		
		ServiceInstanceState instanceState = impersonatedStateModifier.get();
		instanceState.setProgress(task.getLifecycle());
		impersonatedStateModifier.put(instanceState);
		instancesState.put(task.getStateId(), instanceState);

	}
	
	@TaskConsumer
	public void removeServiceInstance(RemoveServiceInstanceFromAgentTask task) {
		
		final URI instanceId = task.getInstanceId();
		this.state.removeServiceInstanceId(instanceId);
		this.instancesState.remove(instanceId);
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
			instanceState.setAgentId(agentId);
			instanceState.setServiceId(serviceId);
		}
		else {
			Preconditions.checkState(instanceState.getAgentId().equals(agentId));
			Preconditions.checkState(instanceState.getServiceId().equals(serviceId));
			instanceState.setUnreachable(false);
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
		state.setProgress(AgentState.Progress.MACHINE_MARKED_FOR_TERMINATION);
	}
	
	@TaskConsumerStateHolder
	public AgentState getState() {
		return state;
	}


}
