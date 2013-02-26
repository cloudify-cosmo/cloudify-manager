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
package org.cloudifysource.cosmo.mock;

import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.ImpersonatingTaskConsumer;
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.tasks.*;

import java.net.URI;
import java.util.Map;

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
        instanceState.setLifecycle(task.getLifecycle());
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
            instanceState.setStateMachine(task.getStateMachine());
            instanceState.setLifecycle(task.getStateMachine().getInitialLifecycle());
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

    @TaskConsumerStateHolder
    public AgentState getState() {
        return state;
    }


}
