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

import org.cloudifysource.cosmo.ImpersonatingTaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerState;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.MachineLifecycleTask;

import java.net.URI;

public class MockMachineProvisioner {

    private final TaskConsumerState state = new TaskConsumerState();
    private final TaskConsumerRegistrar taskConsumerRegistrar;

    public MockMachineProvisioner(TaskConsumerRegistrar taskConsumerRegistrar) {
        this.taskConsumerRegistrar = taskConsumerRegistrar;
    }

    @ImpersonatingTaskConsumer
    public void machineLifecycle(MachineLifecycleTask task,
                                 TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {

        final AgentState agentState = impersonatedStateModifier.get();
        final String lifecycle = task.getLifecycle();
        final URI agentId = task.getStateId();
        if (lifecycle.equals(agentState.getMachineReachableLifecycle())) {
            machineReachable(agentState, agentId);
        } else if (lifecycle.equals(agentState.getMachineStartedLifecycle())) {
            machineStarted(agentState);
        } else if (lifecycle.equals(agentState.getMachineTerminatedLifecycle())) {
            machineTerminated(agentId);
        }

        agentState.setLifecycle(lifecycle);
        impersonatedStateModifier.put(agentState);
    }

    private void machineTerminated(URI agentId) {
        taskConsumerRegistrar.unregisterTaskConsumer(agentId);
    }

    private void machineStarted(AgentState impersonatedState) {
        impersonatedState.incrementNumberOfMachineStarts();
        impersonatedState.resetNumberOfAgentStarts();
    }

    private void machineReachable(AgentState impersonatedState, URI agentId) {
        impersonatedState.incrementNumberOfAgentStarts();
        taskConsumerRegistrar.registerTaskConsumer(new MockAgent(impersonatedState), agentId);
    }

    @TaskConsumerStateHolder
    public TaskConsumerState getState() {
        return state;
    }

}
