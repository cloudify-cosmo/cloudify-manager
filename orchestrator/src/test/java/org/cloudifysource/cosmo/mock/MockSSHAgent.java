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

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Charsets;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import net.schmizz.sshj.SSHClient;
import net.schmizz.sshj.connection.channel.direct.Session;
import net.schmizz.sshj.sftp.SFTPClient;
import net.schmizz.sshj.transport.verification.PromiscuousVerifier;
import net.schmizz.sshj.xfer.InMemoryDestFile;
import net.schmizz.sshj.xfer.InMemorySourceFile;
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
import org.cloudifysource.cosmo.streams.StreamUtils;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;

/**
 * A mock that executes tasks using ssh. This mock stores the service instance
 * state in a file on a remote machine.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class MockSSHAgent {

    private static final int PORT = 22;
    private static final String ROOT = "/export/users/dank/agent/services/";

    private static final ObjectMapper MAPPER = StreamUtils.newObjectMapper();

    private final AgentSSHClient sshClient;
    private final AgentState state;

    public static MockSSHAgent newAgentOnCleanMachine(AgentState state) {
        MockSSHAgent agent = new MockSSHAgent(state);
        try {
            agent.clearPersistedServiceInstanceData();
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
        return agent;
    }

    public static MockSSHAgent newRestartedAgentOnSameMachine(MockSSHAgent agent) {
        Preconditions.checkNotNull(agent, "agent");
        AgentState state = agent.getState();
        Preconditions.checkState(state.isMachineReachableLifecycle());
        state.incrementNumberOfAgentStarts();
        agent.close();
        return new MockSSHAgent(state);
    }

    private MockSSHAgent(AgentState state) {
        this.state = state;
        try {
            this.sshClient = new AgentSSHClient(state.getHost(), PORT, state.getUserName(), state.getKeyFile());
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    @ImpersonatingTaskConsumer
    public void serviceInstanceLifecycle(ServiceInstanceTask task,
                                         TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier)
        throws IOException {
        ServiceInstanceState instanceState = impersonatedStateModifier.get();
        instanceState.getStateMachine().setCurrentState(task.getLifecycleState());
        instanceState.setReachable(true);
        impersonatedStateModifier.put(instanceState);
        writeServiceInstanceState(instanceState, task.getStateId());
    }

    @TaskConsumer
    public void removeServiceInstance(RemoveServiceInstanceFromAgentTask task) throws IOException {
        final URI instanceId = task.getInstanceId();
        this.state.removeServiceInstanceId(instanceId);
        deleteServiceInstanceState(instanceId);
    }

    @ImpersonatingTaskConsumer
    public void recoverServiceInstanceState(RecoverServiceInstanceStateTask task,
                                            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier)
        throws IOException {
        URI instanceId = task.getStateId();
        URI agentId = task.getConsumerId();
        URI serviceId = task.getServiceId();
        Preconditions.checkArgument(
                state.getServiceInstanceIds().contains(instanceId), "Wrong impersonating target: " + instanceId);
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
        impersonatedStateModifier.put(instanceState);
    }

    @ImpersonatingTaskConsumer
    public void injectPropertyToInstance(
            SetInstancePropertyTask task,
            TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) throws IOException {
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
        state.setLastPingSourceTimestamp(task.getProducerTimestamp());
    }

    @TaskConsumerStateHolder
    public AgentState getState() {
        return state;
    }

    public void close() {
        sshClient.close();
    }

    private Optional<ServiceInstanceState> readServiceInstanceState(URI instanceId) throws IOException {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        Optional<String> instanceStateJSON = sshClient.readString(remotePath.fullPath());
        if (instanceStateJSON.isPresent()) {
            return Optional.of(StreamUtils.fromJson(MAPPER, instanceStateJSON.get(), ServiceInstanceState.class));
        }
        return Optional.absent();
    }

    private void writeServiceInstanceState(ServiceInstanceState instanceState, URI instanceId) throws IOException {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        sshClient.writeString(remotePath.pathToParent, remotePath.name, StreamUtils.toJson(MAPPER, instanceState));
    }

    private void deleteServiceInstanceState(URI instanceId) throws IOException {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        sshClient.removeFileIfExists(remotePath.fullPath());
    }

    private InstanceStateRemotePath createRemotePath(URI instanceId) {
        Preconditions.checkNotNull(instanceId, "instanceId");
        InstanceStateRemotePath remotePath = new InstanceStateRemotePath();
        remotePath.pathToParent = ROOT;
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

    private void clearPersistedServiceInstanceData() throws IOException {
        sshClient.removeDirIfExists(ROOT);
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

    // TODO cache already created directory so we don't have to call mkdirs all the time
    /**
     * Helper class to perform basic file operations on a remote machine using ssh.
     */
    private static class AgentSSHClient {

        private final SSHClient sshClient;
        private final SFTPClient sftpClient;

        public AgentSSHClient(String host, int port, String userName, String keyFile) throws IOException {
            sshClient = new SSHClient();
            sshClient.addHostKeyVerifier(new PromiscuousVerifier());
            sshClient.connect(host, port);
            sshClient.authPublickey(userName, keyFile);
            sftpClient = sshClient.newSFTPClient();
        }

        public void writeString(String parentRemotePath, String name, String content) throws IOException {
            sftpClient.mkdirs(parentRemotePath);
            sftpClient.put(new StringSourceFile(name, content), parentRemotePath + name);
        }

        public Optional<String> readString(String remotePath) throws IOException {
            if (sftpClient.statExistence(remotePath) == null) {
                return Optional.absent();
            }
            StringDestFile destFile = new StringDestFile();
            sftpClient.get(remotePath, destFile);
            return Optional.of(destFile.getContent());
        }

        public void removeFileIfExists(String remotePath) throws IOException {
            if (sftpClient.statExistence(remotePath) != null) {
                sftpClient.rm(remotePath);
            }
        }

        public void removeDirIfExists(String remoteDir) throws IOException {
            if (sftpClient.statExistence(remoteDir) != null) {
                executeSingleCommand("rm -r " + remoteDir);
            }
        }

        private void executeSingleCommand(String command) throws IOException {
            Session session = sshClient.startSession();
            try {
                session.exec(command);
            } finally {
                session.close();
            }
        }

        public void close() {
            try {
                sftpClient.close();
            } catch (IOException e) {
                // do nothing
            }
            try {
                sshClient.close();
            } catch (IOException e) {
                // do nothing
            }
        }
    }

    /**
     * {@link InMemorySourceFile} implementation that takes a {@link String} as its input.
     */
    private static class StringSourceFile extends InMemorySourceFile {

        private final String name;
        private final byte[] bytes;

        public StringSourceFile(String name, String content) {
            this.name = name;
            this.bytes = content.getBytes(Charsets.UTF_8);
        }

        @Override
        public String getName() {
            return name;
        }

        @Override
        public long getLength() {
            return bytes.length;
        }

        @Override
        public InputStream getInputStream() throws IOException {
            return new ByteArrayInputStream(bytes);
        }
    }

    /**
     * {@link InMemoryDestFile} implementations that stores the output in a byte array.
     */
    private static class StringDestFile extends InMemoryDestFile {
        private final ByteArrayOutputStream outputStream = new ByteArrayOutputStream();

        @Override
        public OutputStream getOutputStream() throws IOException {
            return outputStream;
        }

        public String getContent() {
            return new String(outputStream.toByteArray(), Charsets.UTF_8);
        }
    }

}
