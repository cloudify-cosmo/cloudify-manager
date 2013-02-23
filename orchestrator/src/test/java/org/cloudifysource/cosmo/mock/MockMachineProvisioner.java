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
import org.cloudifysource.cosmo.ImpersonatingTaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerState;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.StartAgentTask;
import org.cloudifysource.cosmo.agent.tasks.StartMachineTask;
import org.cloudifysource.cosmo.agent.tasks.TerminateMachineOfNonResponsiveAgentTask;
import org.cloudifysource.cosmo.agent.tasks.TerminateMachineTask;

import java.net.URI;

public class MockMachineProvisioner {

    private final TaskConsumerState state = new TaskConsumerState();
    private final TaskConsumerRegistrar taskConsumerRegistrar;

    public MockMachineProvisioner(TaskConsumerRegistrar taskConsumerRegistrar) {
        this.taskConsumerRegistrar = taskConsumerRegistrar;
    }

    @ImpersonatingTaskConsumer
    public void startMachine(StartMachineTask task,
            TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {

        //Simulate starting machine
        final AgentState impersonatedState = impersonatedStateModifier.get();
        Preconditions.checkState(impersonatedState.isProgress(AgentState.Progress.PLANNED));
        //Immediately machine start

        impersonatedState.setProgress(AgentState.Progress.MACHINE_STARTED);
        impersonatedStateModifier.put(impersonatedState);
    }

    @ImpersonatingTaskConsumer
    public void terminateMachineOfNonResponsiveAgent(TerminateMachineOfNonResponsiveAgentTask task, TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {
        final AgentState impersonatedState = impersonatedStateModifier.get();
        Preconditions.checkState(impersonatedState.isProgress(AgentState.Progress.AGENT_STARTED));
        final URI agentId = task.getStateId();
        taskConsumerRegistrar.unregisterTaskConsumer(agentId);
        impersonatedState.setProgress(AgentState.Progress.MACHINE_TERMINATED);
        impersonatedStateModifier.put(impersonatedState);
    }

    @ImpersonatingTaskConsumer
    public void terminateMachine(TerminateMachineTask task, TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {
        final AgentState agentState = impersonatedStateModifier.get();
        Preconditions.checkState(
                agentState.isProgress(
                        AgentState.Progress.MACHINE_MARKED_FOR_TERMINATION,
                        AgentState.Progress.MACHINE_STARTED,
                        AgentState.Progress.PLANNED));

        // code that makes sure the agent is no longer running and
        // cannot change its own state comes here
        final URI agentId = task.getStateId();
        taskConsumerRegistrar.unregisterTaskConsumer(agentId);

        //actual code that terminates machine comes here

        agentState.setProgress(AgentState.Progress.MACHINE_TERMINATED);
        impersonatedStateModifier.put(agentState);

    }

    @ImpersonatingTaskConsumer
    public void startAgent(StartAgentTask task,
            TaskConsumerStateModifier<AgentState> impersonatedStateModifier) {

        final AgentState agentState = impersonatedStateModifier.get();
        Preconditions.checkNotNull(agentState);
        Preconditions.checkState(agentState.isProgress(AgentState.Progress.MACHINE_STARTED));
        final URI agentId = task.getStateId();
        Preconditions.checkState(agentId.toString().endsWith("/"));
        agentState.setProgress(AgentState.Progress.AGENT_STARTED);
        taskConsumerRegistrar.registerTaskConsumer(new MockAgent(agentState), agentId);
        impersonatedStateModifier.put(agentState);
    }

    @TaskConsumerStateHolder
    public TaskConsumerState getState() {
        return state;
    }

}
