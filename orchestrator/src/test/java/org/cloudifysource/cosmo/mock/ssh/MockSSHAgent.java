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

package org.cloudifysource.cosmo.mock.ssh;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Joiner;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.ImpersonatingTaskConsumer;
import org.cloudifysource.cosmo.TaskConsumer;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskConsumerStateModifier;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.tasks.RecoverServiceInstanceStateTask;
import org.cloudifysource.cosmo.service.tasks.RemoveServiceInstanceFromAgentTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
import org.cloudifysource.cosmo.streams.StreamUtils;

import java.io.File;
import java.net.URI;
import java.util.Map;
import java.util.Set;

/**
 * A mock that executes tasks using ssh. This mock stores the service instance
 * state in a file on a remote machine.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class MockSSHAgent {

    private final String agentHome;
    private final String servicesRoot;
    private final String scriptsRoot;

    private static final Logger LOG = LoggerFactory.getLogger(MockSSHAgent.class);

    private static final ObjectMapper MAPPER = StreamUtils.newObjectMapper();

    private final AgentSSHClient sshClient;
    private final AgentState state;
    private final Set<String> createdServiceInstanceDirectories = Sets.newCopyOnWriteArraySet();

    public static MockSSHAgent newAgentOnCleanMachine(AgentState state) {
        MockSSHAgent agent = new MockSSHAgent(state);
        agent.clearPersistedServiceInstanceData();
        return agent;
    }

    public static MockSSHAgent newRestartedAgentOnSameMachine(MockSSHAgent agent) {
        Preconditions.checkNotNull(agent, "agent");
        AgentState state = agent.getState();
        Preconditions.checkState(state.isMachineReachableLifecycle());
        state.incrementNumberOfAgentStarts();
        agent.close();
        MockSSHAgent newAgent = new MockSSHAgent(state);
        newAgent.createdServiceInstanceDirectories.addAll(agent.createdServiceInstanceDirectories);
        return newAgent;
    }

    // TODO SSH refactor/extract constants
    private MockSSHAgent(AgentState state) {
        this.state = state;
        String agentHome = Preconditions.checkNotNull(state.getStateMachine().getProperties().get("agenthome"));
        if (!agentHome.endsWith("/")) {
            agentHome += "/";
        }
        this.agentHome = agentHome;
        this.servicesRoot = agentHome + "services/";
        this.scriptsRoot = agentHome + "scripts";
        String host = Preconditions.checkNotNull(state.getStateMachine().getProperties().get("ip"));
        String userName = Preconditions.checkNotNull(state.getStateMachine().getProperties().get("username"));
        String keyFile = Preconditions.checkNotNull(state.getStateMachine().getProperties().get("keyfile"));
        String port = state.getStateMachine().getProperties().get("port");
        if (port == null) {
            port = "22";
        }
        this.sshClient = new AgentSSHClient(host, Integer.parseInt(port), userName, keyFile);
    }

    @ImpersonatingTaskConsumer
    public void serviceInstanceLifecycle(ServiceInstanceTask task,
                                         TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
        ServiceInstanceState instanceState = impersonatedStateModifier.get();
        instanceState.getStateMachine().setCurrentState(task.getLifecycleState());
        instanceState.setReachable(true);
        impersonatedStateModifier.put(instanceState);
        writeServiceInstanceState(instanceState, task.getStateId());
        handleServiceInstanceLifecycle(instanceState);
    }

    private void handleServiceInstanceLifecycle(ServiceInstanceState instanceState) {
        LifecycleStateMachine lifecycleStateMachine = instanceState.getStateMachine();
        LifecycleName lifecycleName = lifecycleStateMachine.getLifecycleName();
        if ("file".equals(lifecycleName.getName())) {
            putFileInRemoteMachine(lifecycleStateMachine, lifecycleName);
        } else {
            executeLifecycleStateScript(lifecycleStateMachine);
        }
    }

    @TaskConsumer
    public void removeServiceInstance(RemoveServiceInstanceFromAgentTask task) {
        final URI instanceId = task.getInstanceId();
        this.state.removeServiceInstanceId(instanceId);
        deleteServiceInstanceState(instanceId);
    }

    @ImpersonatingTaskConsumer
    public void recoverServiceInstanceState(RecoverServiceInstanceStateTask task,
                                            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
        URI instanceId = task.getStateId();
        URI agentId = task.getConsumerId();
        URI serviceId = task.getServiceId();

        Optional<ServiceInstanceState> optionalInstanceState = readServiceInstanceState(instanceId);
        ServiceInstanceState instanceState;
        if (!optionalInstanceState.isPresent()) {
            instanceState = new ServiceInstanceState();
            instanceState.setAgentId(agentId);
            instanceState.setServiceId(serviceId);
            LifecycleStateMachine stateMachine = task.getStateMachine();
            stateMachine.setCurrentState(stateMachine.getBeginState());
            instanceState.setStateMachine(stateMachine);
            instanceState.setReachable(true);
        } else {
            instanceState = optionalInstanceState.get();
            Preconditions.checkState(instanceState.getAgentId().equals(agentId));
            Preconditions.checkState(instanceState.getServiceId().equals(serviceId));
            Preconditions.checkState(instanceState.isReachable());
        }

        if (!state.getServiceInstanceIds().contains(instanceId)) {
            state.addServiceInstance(instanceId);
        }

        impersonatedStateModifier.put(instanceState);
    }

    @ImpersonatingTaskConsumer
    public void injectPropertyToInstance(
            SetInstancePropertyTask task,
            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
        final URI instanceId = task.getStateId();
        Optional<ServiceInstanceState> optionalInstanceState = readServiceInstanceState(instanceId);
        Preconditions.checkState(optionalInstanceState.isPresent(), "missing service instance state");
        ServiceInstanceState instanceState = optionalInstanceState.get();
        instanceState.setProperty(task.getPropertyName(), task.getPropertyValue());
        impersonatedStateModifier.put(instanceState);
        writeServiceInstanceState(instanceState, task.getStateId());
    }

    @TaskConsumer(noHistory = true)
    public void ping(PingAgentTask task) {
        try {
            int exitCode = sshClient.executeSingleCommand("echo ping");
            if (exitCode == 0) {
                state.setLastPingSourceTimestamp(task.getProducerTimestamp());
                state.getStateMachine().setCurrentState(state.getMachineReachableLifecycle());
            }
        } catch (Exception e) {
            LOG.debug("Ping failed", e);
        }
    }

    @TaskConsumerStateHolder
    public AgentState getState() {
        return state;
    }

    public void close() {
        sshClient.close();
    }

    private Optional<ServiceInstanceState> readServiceInstanceState(URI instanceId) {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        Optional<String> instanceStateJSON = sshClient.getString(remotePath.fullPath());
        if (instanceStateJSON.isPresent()) {
            return Optional.of(StreamUtils.fromJson(MAPPER, instanceStateJSON.get(), ServiceInstanceState.class));
        }
        return Optional.absent();
    }

    private void writeServiceInstanceState(ServiceInstanceState instanceState, URI instanceId) {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        boolean mkdirs = !createdServiceInstanceDirectories.contains(remotePath.pathToParent);
        sshClient.putString(remotePath.pathToParent, remotePath.name, StreamUtils.toJson(MAPPER, instanceState),
                mkdirs);
        // only add to cache upon successful operation
        if (mkdirs) {
            createdServiceInstanceDirectories.add(remotePath.pathToParent);
        }
    }

    private void putFileInRemoteMachine(LifecycleStateMachine lifecycleStateMachine, LifecycleName lifecycleName) {
        String targetFileName = lifecycleName.getSecondaryName();
        Preconditions.checkNotNull(targetFileName, "lifecycleName.secodaryName");
        // TODO SSH parent extraction logic
        int lastIndexOfPathSeparator = targetFileName.lastIndexOf('/');
        Preconditions.checkArgument(lastIndexOfPathSeparator >= 0, "cannot extract parent path");
        String parentPath = targetFileName.substring(0, lastIndexOfPathSeparator);
        String fileName = targetFileName.substring(lastIndexOfPathSeparator + 1);

        // TODO SSH refactor/extract constants
        if (lifecycleStateMachine.getCurrentState().getName().endsWith("_exists")) {
            String sourceFileName = lifecycleStateMachine.getProperties().get("source");
            Preconditions.checkNotNull(sourceFileName, "lifecycleStateMachine.property(source)");
            sshClient.putFile(parentPath, fileName, new File(sourceFileName), true);
        } else if (lifecycleStateMachine.getCurrentState().getName().endsWith("_cleaned")) {
            sshClient.removeFileIfExists(targetFileName);
        }
    }

    // TODO SSH handle execution errors
    private void executeLifecycleStateScript(LifecycleStateMachine lifecycleStateMachine) {
        LifecycleState lifecycleState = lifecycleStateMachine.getCurrentState();
        LifecycleName lifecycleName = LifecycleName.fromLifecycleState(lifecycleState);
        String scriptName = lifecycleState.getName() + ".sh";
        String workingDirectory = Joiner.on('/').join(scriptsRoot, lifecycleName.getName());
        String scriptPath = Joiner.on('/').join(workingDirectory, scriptName);
        Map<String, String> environmentVariables = Maps.newHashMap();
        environmentVariables.putAll(lifecycleStateMachine.getProperties());
        // TODO SSH refactor/extract constants
        environmentVariables.put("COSMO_HOME", agentHome);
        sshClient.executeScript(workingDirectory, scriptPath, environmentVariables);
    }

    private void deleteServiceInstanceState(URI instanceId) {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        sshClient.removeFileIfExists(remotePath.fullPath());
    }

    private InstanceStateRemotePath createRemotePath(URI instanceId) {
        Preconditions.checkNotNull(instanceId, "instanceId");
        InstanceStateRemotePath remotePath = new InstanceStateRemotePath();
        remotePath.pathToParent = servicesRoot;
        String path = instanceId.getPath();
        if (path.endsWith("/")) {
            path = path.substring(0, path.length() - 1);
        }
        int lastSeperatorIndex = path.lastIndexOf('/');
        if (lastSeperatorIndex == -1) {
            remotePath.name = path;
        } else {
            String suffixPathToParent = path.substring(0, lastSeperatorIndex + 1);
            if (suffixPathToParent.startsWith("/")) {
                suffixPathToParent = suffixPathToParent.substring(1);
            }
            remotePath.pathToParent += suffixPathToParent;
            remotePath.name = path.substring(lastSeperatorIndex + 1);
        }

        // add 'generation'
        remotePath.pathToParent += (state.getNumberOfMachineStarts() + "/");

        return remotePath;
    }

    private void clearPersistedServiceInstanceData() {
        sshClient.removeDirIfExists(servicesRoot);
    }

    public AgentSSHClient getSSHClient() {
        return sshClient;
    }

    public String getScriptsRoot() {
        return scriptsRoot;
    }

    /**
     * Holds parent path and file name for instance states.
     */
    private static class InstanceStateRemotePath {
        String pathToParent;
        String name;

        String fullPath() {
            return pathToParent + name;
        }
    }
}
