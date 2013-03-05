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
import com.google.common.collect.ImmutableSet;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.StateClient;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.TaskWriter;
import org.cloudifysource.cosmo.agent.health.TaskBasedAgentHealthProbe;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.kvstore.KVStoreServer;
import org.cloudifysource.cosmo.service.ServiceGridOrchestrator;
import org.cloudifysource.cosmo.service.ServiceGridOrchestratorParameter;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.state.ServiceGridDeploymentPlan;
import org.cloudifysource.cosmo.service.state.ServiceGridOrchestratorState;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.state.StateWriter;
import org.cloudifysource.cosmo.streams.StreamUtils;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;
import org.cloudifysource.cosmo.time.MockCurrentTimeProvider;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.List;

/**
 * Creates the various management components needed for unit testing.
 * @author itaif
 * @since 0.1
 */
public class MockManagement {

    private static final int STATE_SERVER_PORT = 8080;
    private static final String STATE_SERVER_URI = "http://localhost:" + STATE_SERVER_PORT + "/";
    private static final boolean USE_MOCK = true;
    private final URI orchestratorId;
    private final URI agentProbeId;
    private final URI machineProvisionerId;
    private final StateReader stateReader;
    private final StateWriter stateWriter;
    private final MockTaskBroker taskBroker;
    private MockCurrentTimeProvider timeProvider;
    private List<URI> taskConsumersToUnregisterOnClose;

    public void setTaskConsumerRegistrar(TaskConsumerRegistrar taskConsumerRegistrar) {
        this.taskConsumerRegistrar = taskConsumerRegistrar;
    }

    public void setTimeProvider(MockCurrentTimeProvider timeProvider) {
        this.timeProvider = timeProvider;
    }

    private TaskConsumerRegistrar taskConsumerRegistrar;
    private final MockTaskBroker persistentTaskBroker;
    private KVStoreServer stateServer;

    public MockManagement()  {

        agentProbeId = createUri("services/agentprobe/");
        orchestratorId = createUri("services/orchestrator/");
        machineProvisionerId = createUri("services/provisioner/");

        if (USE_MOCK) {
            stateReader = new MockState();
            stateWriter = (StateWriter) stateReader;
            ((MockState) stateReader).setLoggingEnabled(false);
        } else {
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
            return new URI(STATE_SERVER_URI + relativeId);
        } catch (URISyntaxException e) {
            throw Throwables.propagate(e);
        }
    }

    public URI getOrchestratorId() {
        return orchestratorId;
    }

    public URI getAgentProbeId() {
        return agentProbeId;
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
        stop();
        clearState();
        taskBroker.clear();
        registerTaskConsumers();
    }

    private void clearState() {
        if (USE_MOCK) {
            ((MockState) stateReader).clear();
        } else {
            stateServer.reload();
        }
    }

    public void start() {

        taskConsumersToUnregisterOnClose = Lists.newArrayList();
        clearState();
        taskBroker.clear();
        persistentTaskBroker.clear();
        registerTaskConsumers();
    }

    public void unregisterTaskConsumers() {
        unregisterTaskConsumer(agentProbeId);
        unregisterTaskConsumer(orchestratorId);
        unregisterTaskConsumer(machineProvisionerId);
    }

    protected void registerTaskConsumers() {
        TaskBasedAgentHealthProbe taskBasedAgentHealthProbe = newAgentProbe(timeProvider);
        registerTaskConsumer(taskBasedAgentHealthProbe, agentProbeId);
        registerTaskConsumer(newServiceGridOrchestrator(timeProvider, taskBasedAgentHealthProbe), orchestratorId);
        registerTaskConsumer(newMachineProvisionerContainer(taskConsumerRegistrar), machineProvisionerId);
    }

    protected void registerTaskConsumer(Object taskConsumer, URI taskConsumerId) {
        this.taskConsumersToUnregisterOnClose.add(taskConsumerId);
        taskConsumerRegistrar.registerTaskConsumer(taskConsumer, taskConsumerId);
    }

    protected void unregisterTaskConsumer(URI taskConsumerId) {
        taskConsumerRegistrar.unregisterTaskConsumer(taskConsumerId);
        taskConsumersToUnregisterOnClose.remove(taskConsumerId);
    }

    private TaskBasedAgentHealthProbe newAgentProbe(CurrentTimeProvider timeProvider) {
        return new TaskBasedAgentHealthProbe(timeProvider, taskBroker,
                stateReader, agentProbeId);
    }

    private ServiceGridOrchestrator newServiceGridOrchestrator(CurrentTimeProvider timeProvider,
                                                               TaskBasedAgentHealthProbe taskBasedAgentHealthProbe) {

        final ServiceGridOrchestratorParameter serviceOrchestratorParameter = new ServiceGridOrchestratorParameter();
        serviceOrchestratorParameter.setOrchestratorId(orchestratorId);
        serviceOrchestratorParameter.setMachineProvisionerId(machineProvisionerId);
        serviceOrchestratorParameter.setStateReader(stateReader);
        serviceOrchestratorParameter.setTimeProvider(timeProvider);
<<<<<<< HEAD
        serviceOrchestratorParameter.setServerId(getStateServerUri());
=======
        serviceOrchestratorParameter.setAgentHealthProbe(taskBasedAgentHealthProbe);
>>>>>>> origin/develop

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
        if (!USE_MOCK) {
            stateServer.stop();
        }
    }

    public URI getStateServerUri() {
        return URI.create(STATE_SERVER_URI);
    }

    protected MockCurrentTimeProvider getTimeProvider() {
        return timeProvider;
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
        task.setProducerId(ServiceUtils.newServiceId(getStateServerUri(), "webui/", new LifecycleName("tomcat")));
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

    public ServiceGridDeploymentPlan getDeploymentPlan() {
        return getStateReader()
                .get(getOrchestratorId(), ServiceGridOrchestratorState.class)
                .getState()
                .getDeploymentPlan();
    }

    public void stop() {
        for (URI taskConsumerId : ImmutableSet.copyOf(taskConsumersToUnregisterOnClose)) {
            unregisterTaskConsumer(taskConsumerId);
        }
    }

<<<<<<< HEAD
    public URI getServiceId(String aliasGroup, LifecycleName lifecycleName) {
        return ServiceUtils.newServiceId(getStateServerUri(), aliasGroup, lifecycleName);
    }

    public URI getServiceInstanceId(String alias, LifecycleName lifecycleName) {
        return ServiceUtils.newInstanceId(getStateServerUri(), alias, lifecycleName);
    }

    public URI getAgentId(String alias) {
        return ServiceUtils.newAgentId(getStateServerUri(), alias);
    }
=======

>>>>>>> origin/develop
}

