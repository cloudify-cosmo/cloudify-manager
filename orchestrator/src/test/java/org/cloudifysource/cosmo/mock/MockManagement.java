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

import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.StateClient;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.TaskWriter;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.kvstore.KVStoreServer;
import org.cloudifysource.cosmo.service.*;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.state.StateWriter;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;
import org.cloudifysource.cosmo.time.MockCurrentTimeProvider;

import java.net.URI;
import java.net.URISyntaxException;

public class MockManagement {

    private static final int STATE_SERVER_PORT = 8080;
    private static final String STATE_SERVER_URI = "http://localhost:"+STATE_SERVER_PORT+"/";
    private static final boolean useMock = true;
    private final URI orchestratorId;
    private final URI machineProvisionerId;
    private final StateReader stateReader;
    private final StateWriter stateWriter;
    private final MockTaskBroker taskBroker;
    private MockCurrentTimeProvider timeProvider;

    public void setTaskConsumerRegistrar(TaskConsumerRegistrar taskConsumerRegistrar) {
        this.taskConsumerRegistrar = taskConsumerRegistrar;
    }

    public void setTimeProvider(MockCurrentTimeProvider timeProvider) {
        this.timeProvider = timeProvider;
    }

    private TaskConsumerRegistrar taskConsumerRegistrar;
    private final MockTaskBroker persistentTaskBroker;
    private KVStoreServer stateServer;
    private final URI agentsId;

    public MockManagement()  {

        orchestratorId = createUri("services/orchestrator/");
        machineProvisionerId = createUri("services/provisioner/");
        agentsId = createUri("agents/");

        if (useMock) {
            stateReader = new MockState();
            stateWriter = (StateWriter) stateReader;
            ((MockState)stateReader).setLoggingEnabled(false);
        }
        else {
            stateReader = new StateClient(StreamUtils.newURI(STATE_SERVER_URI));
            stateWriter = (StateWriter) stateReader;
            stateServer = new KVStoreServer();
            stateServer.start(STATE_SERVER_PORT);
        }
        taskBroker = new MockTaskBroker();
        taskBroker.setLoggingEnabled(false);
        persistentTaskBroker = new MockTaskBroker();

    }

    protected URI createUri(String relativeId) {
        try {
            return new URI(STATE_SERVER_URI+ relativeId);
        } catch (URISyntaxException e) {
            throw Throwables.propagate(e);
        }
    }

    public URI getOrchestratorId() {
        return orchestratorId;
    }

    public TaskReader getTaskReader() {
        return taskBroker;
    }

    public TaskWriter getTaskWriter() {
        return taskBroker;
    }

    public StateReader getStateReader() {
        return stateReader;
    }

    public StateWriter getStateWriter() {
        return stateWriter;
    }

    public void restart() {
        unregisterTaskConsumers();
        clearState();
        taskBroker.clear();
        registerTaskConsumers();
    }

    private void clearState() {
        if (useMock) {
            ((MockState)stateReader).clear();
        }
        else {
            stateServer.reload();
        }
    }

    public void start() {

        clearState();
        taskBroker.clear();
        persistentTaskBroker.clear();
        registerTaskConsumers();
    }

    public void unregisterTaskConsumers() {
        unregisterTaskConsumer(orchestratorId);
        unregisterTaskConsumer(machineProvisionerId);
    }

    protected void registerTaskConsumers() {
        registerTaskConsumer(newServiceGridOrchestrator(timeProvider), orchestratorId);
        registerTaskConsumer(newMachineProvisionerContainer(taskConsumerRegistrar), machineProvisionerId);
    }

    protected void registerTaskConsumer(Object taskConsumer, URI taskConsumerId) {
        taskConsumerRegistrar.registerTaskConsumer(taskConsumer, taskConsumerId);
    }

    protected void unregisterTaskConsumer(URI taskConsumerId) {
        taskConsumerRegistrar.unregisterTaskConsumer(taskConsumerId);
    }

    private ServiceGridOrchestrator newServiceGridOrchestrator(CurrentTimeProvider timeProvider) {

        final ServiceGridOrchestratorParameter serviceOrchestratorParameter = new ServiceGridOrchestratorParameter();
        serviceOrchestratorParameter.setOrchestratorId(orchestratorId);
        serviceOrchestratorParameter.setMachineProvisionerId(machineProvisionerId);
        serviceOrchestratorParameter.setTaskReader(taskBroker);
        serviceOrchestratorParameter.setStateReader(stateReader);
        serviceOrchestratorParameter.setTimeProvider(timeProvider);

        return new ServiceGridOrchestrator(serviceOrchestratorParameter);
    }

    private MockMachineProvisioner newMachineProvisionerContainer(TaskConsumerRegistrar taskConsumerRegistrar) {
        return new MockMachineProvisioner(taskConsumerRegistrar);
    }

    public TaskReader getPersistentTaskReader() {
        return persistentTaskBroker;
    }

    public TaskWriter getPersistentTaskWriter() {
        return persistentTaskBroker;
    }

    public void close() {
        if (!useMock) {
            stateServer.stop();
        }
    }

    public URI getStateServerUri() {
        return StreamUtils.newURI(STATE_SERVER_URI);
    }

    protected MockCurrentTimeProvider getTimeProvider() {
        return timeProvider;
    }

    public URI getAgentsId() {
        return agentsId;
    }

    public URI getAgentId(int index) {
        return ServiceUtils.newAgentId(getAgentsId(), index);
    }

    public URI getServiceId(String name) {
        return ServiceUtils.newServiceId(getStateServerUri(), name);
    }

    public URI getServiceInstanceId(final String serviceName, final int index) {
        return ServiceUtils.newInstanceId(getStateServerUri(), serviceName, index);
    }

    public AgentState getAgentState(URI agentId) {
        return ServiceUtils.getAgentState(getStateReader(), agentId);
    }

    public ServiceState getServiceState(URI serviceId) {
        return ServiceUtils.getServiceState(getStateReader(), serviceId);
    }

    public ServiceInstanceState getServiceInstanceState(URI instanceId) {
        return ServiceUtils.getServiceInstanceState(getStateReader(), instanceId);
    }

    public void submitTask(URI target, Task task) {
        task.setProducerTimestamp(timeProvider.currentTimeMillis());
        task.setProducerId(getServiceId("webui"));
        task.setConsumerId(target);
        getTaskWriter().postNewTask(task);
    }

    public MockTaskContainer newContainer(URI executorId, Object taskConsumer) {

        MockTaskContainerParameter containerParameter = new MockTaskContainerParameter();
        containerParameter.setExecutorId(executorId);
        containerParameter.setTaskConsumer(taskConsumer);
        containerParameter.setStateReader(getStateReader());
        containerParameter.setStateWriter(getStateWriter());
        containerParameter.setTaskReader(getTaskReader());
        containerParameter.setTaskWriter(getTaskWriter());
        containerParameter.setPersistentTaskReader(getPersistentTaskReader());
        containerParameter.setPersistentTaskWriter(getPersistentTaskWriter());
        containerParameter.setTimeProvider(timeProvider);
        return new MockTaskContainer(containerParameter);
    }
}

