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
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.tasks.RecoverServiceInstanceStateTask;
import org.cloudifysource.cosmo.service.tasks.RemoveServiceInstanceFromAgentTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;

/**
 * A mock agent that does nothing when recieves a task.
 * @author itaif
 * @since 0.1
 */
public class MockZombieAgent {

    private final AgentState state;

    public static MockZombieAgent newZombieAgent(AgentState state) {
        return new MockZombieAgent(state);
    }

    private MockZombieAgent(AgentState state) {
        this.state = state;
    }

    @ImpersonatingTaskConsumer
    public void serviceInstanceLifecycle(ServiceInstanceTask task,
                                         TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
        // do nothing
    }

    @TaskConsumer
    public void removeServiceInstance(RemoveServiceInstanceFromAgentTask task) {

        // do nothing
    }

    @ImpersonatingTaskConsumer
    public void recoverServiceInstanceState(RecoverServiceInstanceStateTask task,
                                            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {

        // do nothing
    }

    @ImpersonatingTaskConsumer
    public void injectPropertyToInstance(
            SetInstancePropertyTask task,
            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {

        // do nothing
    }

    @TaskConsumer(noHistory = true)
    public void ping(PingAgentTask task) {
        // do nothing
    }

    @TaskConsumerStateHolder
    public AgentState getState() {
        return state;
    }
}
