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
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.tasks.RecoverServiceInstanceStateTask;
import org.cloudifysource.cosmo.service.tasks.RemoveServiceInstanceFromAgentTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;

import java.net.URI;
import java.util.Map;

/**
 * A mock that executes tasks that should be executed by an Agent in the real world.
 * @author itaif
 * @since 0.1
 */
public class MockAgent {

    private final AgentState state;
    private final Map<URI, ServiceInstanceState> instancesState;

    public static MockAgent newAgentOnCleanMachine(AgentState state) {
        return new MockAgent(state, Maps.<URI, ServiceInstanceState>newLinkedHashMap());
    }

    public static MockAgent newRestartedAgentOnSameMachine(MockAgent agent) {
        AgentState state = agent.getState();
        Preconditions.checkState(state.isMachineReachableLifecycle());
        state.incrementNumberOfAgentStarts();
        return new MockAgent(state, agent.instancesState);
    }

    private MockAgent(AgentState state, Map<URI, ServiceInstanceState> instancesState) {
        this.state = state;
        this.instancesState = instancesState;
    }

    @ImpersonatingTaskConsumer
    public void serviceInstanceLifecycle(ServiceInstanceTask task,
            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {

        ServiceInstanceState instanceState = impersonatedStateModifier.get();
        instanceState.getStateMachine().setCurrentState(task.getLifecycleState());
        instanceState.setReachable(true);
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

        ServiceInstanceState instanceState = instancesState.get(instanceId);
        Preconditions.checkArgument(instanceState == null || instanceState.getAgentId().equals(agentId));

        if (!state.getServiceInstanceIds().contains(instanceId)) {
            state.addServiceInstance(instanceId);
        }

        if (instanceState == null) {
            instanceState = new ServiceInstanceState();
            instanceState.setAgentId(agentId);
            instanceState.setServiceId(serviceId);
            final LifecycleStateMachine stateMachine = task.getStateMachine();
            stateMachine.setCurrentState(stateMachine.getBeginState());
            instanceState.setStateMachine(stateMachine);
            instanceState.setReachable(true);
        } else {
            Preconditions.checkState(instanceState.getAgentId().equals(agentId));
            Preconditions.checkState(instanceState.getServiceId().equals(serviceId));
            Preconditions.checkState(instanceState.isReachable());
        }
        impersonatedStateModifier.put(instanceState);
    }

    @ImpersonatingTaskConsumer
    public void injectPropertyToInstance(
            SetInstancePropertyTask task,
            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {

        final URI instanceId = task.getStateId();
        Preconditions.checkArgument(instancesState.containsKey(instanceId), "Unknown instance %s", instanceId);
        ServiceInstanceState instanceState = instancesState.get(instanceId);
        instanceState.setProperty(task.getPropertyName(), task.getPropertyValue());
        impersonatedStateModifier.put(instanceState);
    }

    @TaskConsumer(noHistory = true)
    public void ping(PingAgentTask task) {
        state.setLastPingSourceTimestamp(task.getProducerTimestamp());
        state.setLastPingChallenge(task.getChallenge());
        state.getStateMachine().setCurrentState(state.getMachineReachableLifecycle());
    }

    @TaskConsumerStateHolder
    public AgentState getState() {
        return state;
    }
}
