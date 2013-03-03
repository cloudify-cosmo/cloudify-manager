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
package org.cloudifysource.cosmo.service;

import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;

/**
 * The input for {@link ServiceGridOrchestrator#ServiceGridOrchestrator(ServiceGridOrchestratorParameter)}.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridOrchestratorParameter {

    private URI orchestratorId;
    private URI machineProvisionerId;
    private TaskReader taskReader;
    private StateReader stateReader;
    private CurrentTimeProvider timeProvider;

    public URI getServerId() {
        return serverId;
    }

    public void setServerId(URI serverId) {
        this.serverId = serverId;
    }

    private URI serverId;

    public TaskReader getTaskReader() {
        return taskReader;
    }

    public void setTaskReader(TaskReader taskReader) {
        this.taskReader = taskReader;
    }

    public StateReader getStateReader() {
        return stateReader;
    }

    public void setStateReader(StateReader stateReader) {
        this.stateReader = stateReader;
    }

    public URI getOrchestratorId() {
        return orchestratorId;
    }

    public void setOrchestratorId(URI id) {
        this.orchestratorId = id;
    }

    public URI getMachineProvisionerId() {
        return machineProvisionerId;
    }

    public void setMachineProvisionerId(URI cloudExecutorId) {
        this.machineProvisionerId = cloudExecutorId;
    }

    public CurrentTimeProvider getTimeProvider() {
        return timeProvider;
    }

    public void setTimeProvider(CurrentTimeProvider timeProvider) {
        this.timeProvider = timeProvider;
    }
}
