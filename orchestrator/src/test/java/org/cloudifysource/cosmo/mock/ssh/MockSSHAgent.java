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
import com.google.common.base.Ascii;
import com.google.common.base.Charsets;
import com.google.common.base.Joiner;
import com.google.common.base.Objects;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import net.schmizz.sshj.SSHClient;
import net.schmizz.sshj.connection.channel.ChannelInputStream;
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

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * A mock that executes tasks using ssh. This mock stores the service instance
 * state in a file on a remote machine.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class MockSSHAgent {

    private static final int PORT = 22;
    private static final String SERVICES_ROOT = "/export/users/dank/agent/services/";
    public static final String SCRIPTS_ROOT = "/export/users/dank/agent/scripts";

    private static final Logger LOG = LoggerFactory.getLogger(MockSSHAgent.class);

    private static final ObjectMapper MAPPER = StreamUtils.newObjectMapper();

    private final AgentSSHClient sshClient;
    private final AgentState state;

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
        return new MockSSHAgent(state);
    }

    private MockSSHAgent(AgentState state) {
        this.state = state;
        this.sshClient = new AgentSSHClient(state.getHost(), PORT, state.getUserName(), state.getKeyFile());
    }

    @ImpersonatingTaskConsumer
    public void serviceInstanceLifecycle(ServiceInstanceTask task,
                                         TaskConsumerStateModifier<ServiceInstanceState> impersonatedStateModifier) {
        ServiceInstanceState instanceState = impersonatedStateModifier.get();
        instanceState.getStateMachine().setCurrentState(task.getLifecycleState());
        instanceState.setReachable(true);
        impersonatedStateModifier.put(instanceState);
        writeServiceInstanceState(instanceState, task.getStateId());
        executeLifecycleStateScript(instanceState.getStateMachine());
    }

    @TaskConsumer
    public void removeServiceInstance(RemoveServiceInstanceFromAgentTask task) {
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
        sshClient.putString(remotePath.pathToParent, remotePath.name, StreamUtils.toJson(MAPPER, instanceState));
    }

    // TODO SSH handle execution errors
    private void executeLifecycleStateScript(LifecycleStateMachine lifecycleStateMachine) {
        LifecycleState lifecycleState = lifecycleStateMachine.getCurrentState();
        LifecycleName lifecycleName = LifecycleName.fromLifecycleState(lifecycleState);
        String scriptName = lifecycleState.getName() + ".sh";
        String workingDirectory = Joiner.on('/').join(SCRIPTS_ROOT, lifecycleName.getName());
        String scriptPath = Joiner.on('/').join(workingDirectory, scriptName);
        sshClient.executeScript(workingDirectory, scriptPath, lifecycleStateMachine.getProperties());
    }

    private void deleteServiceInstanceState(URI instanceId) {
        InstanceStateRemotePath remotePath = createRemotePath(instanceId);
        sshClient.removeFileIfExists(remotePath.fullPath());
    }

    private InstanceStateRemotePath createRemotePath(URI instanceId) {
        Preconditions.checkNotNull(instanceId, "instanceId");
        InstanceStateRemotePath remotePath = new InstanceStateRemotePath();
        remotePath.pathToParent = SERVICES_ROOT;
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
        sshClient.removeDirIfExists(SERVICES_ROOT);
    }

    public AgentSSHClient getSSHClient() {
        return sshClient;
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
    public static class AgentSSHClient {

        private final SSHClient sshClient;
        private final SFTPClient sftpClient;
        private final String connectionInfo;

        public AgentSSHClient(String host, int port, String userName, String keyFile) {
            try {
                sshClient = new SSHClient();
                sshClient.addHostKeyVerifier(new PromiscuousVerifier());
                sshClient.connect(host, port);
                sshClient.authPublickey(userName, keyFile);
                sftpClient = sshClient.newSFTPClient();
                connectionInfo = userName + "@" + host + ":" + port;
            } catch (IOException e) {
                throw Throwables.propagate(e);
            }
        }

        public void putString(String parentRemotePath, String name, String content) {
            try {
                sftpClient.mkdirs(parentRemotePath);
                if (!parentRemotePath.endsWith("/")) {
                    parentRemotePath += "/";
                }
                sftpClient.put(new StringSourceFile(name, content), parentRemotePath + name);
            } catch (IOException e) {
                throw Throwables.propagate(e);
            }
        }

        public Optional<String> getString(String remotePath) {
            StringDestFile destFile = new StringDestFile();
            try {
                sftpClient.get(remotePath, destFile);
            } catch (IOException e) {
                return Optional.absent();
            }
            return Optional.of(destFile.getContent());
        }

        public void removeFileIfExists(String remotePath) {
            try {
                sftpClient.rm(remotePath);
            } catch (IOException e) {
                LOG.debug("Failed removing file", e);
            }
        }

        public void removeDirIfExists(String remoteDir) {
            executeSingleCommand("rm -r " + remoteDir);
        }

        public int executeSingleCommand(String command) {
            return execute(command);
        }

        public int executeScript(String workingDirectory, String scriptPath, Map<String,
                String> envVars) {
            List<String> commands = Lists.newLinkedList();
            commands.add("cd " + workingDirectory);
            if (envVars != null) {
                for (Map.Entry<String, String> envVar : envVars.entrySet()) {
                    StringBuilder command = new StringBuilder();
                    command.append("export ").append(envVar.getKey()).append("=").append(envVar.getValue());
                    commands.add(command.toString());
                }
            }
            commands.add("chmod +x " + scriptPath);
            commands.add(scriptPath);
            return execute(Joiner.on(';').join(commands));
        }

        // TODO SSH timeout, sleep between line reads
        private int execute(String command) {
            try {
                Session session = sshClient.startSession();
                try {
                    Session.Command sessionCommand = session.exec(command);
                    SessionCommandNonBlockingLineConsumer lineConsumer =
                            new SessionCommandNonBlockingLineConsumer(sessionCommand);
                    while (sessionCommand.isOpen()) {
                        for (String line : lineConsumer.readAvailableLines()) {
                            LOG.info(SSHOutput.OUT, connectionInfo, line);
                        }
                    }
                    return Objects.firstNonNull(sessionCommand.getExitStatus(), -1);
                } finally {
                    try {
                        session.close();
                    } catch (IOException e) {
                        LOG.debug("Failed closing ssh session", e);
                    }
                }
            } catch (IOException e) {
                throw Throwables.propagate(e);
            }
        }

        public void close() {
            try {
                sftpClient.close();
            } catch (IOException e) {
                LOG.debug("Failed closing sftp client", e);
            }
            try {
                sshClient.close();
            } catch (IOException e) {
                LOG.debug("Failed closing ssh client", e);
            }
        }
    }

    /**
     * Reads lines in a non blocking manner for the given {@link Session.Command}.
     */
    private static class SessionCommandNonBlockingLineConsumer {

        private final ChannelInputStreamNonBlockingLineConsumer stdOutLineConsumer;
        private final ChannelInputStreamNonBlockingLineConsumer stdErrLineConsumer;

        public SessionCommandNonBlockingLineConsumer(Session.Command sessionCommand) {
            stdOutLineConsumer = new ChannelInputStreamNonBlockingLineConsumer(
                    (ChannelInputStream) sessionCommand.getInputStream());
            stdErrLineConsumer = new ChannelInputStreamNonBlockingLineConsumer(
                    (ChannelInputStream) sessionCommand.getErrorStream());
        }

        public List<String> readAvailableLines() {
            List<String> stdOutAvailableLines = stdOutLineConsumer.readAvailableLines();
            List<String> stdErrAvailableLines = stdErrLineConsumer.readAvailableLines();
            if (stdOutAvailableLines.isEmpty()) {
                return stdErrAvailableLines;
            } else {
                stdOutAvailableLines.addAll(stdErrAvailableLines);
                return stdOutAvailableLines;
            }
        }

    }

    /**
     * Reads lines in a non blocking manner for the given {@link ChannelInputStream}.
     */
    private static class ChannelInputStreamNonBlockingLineConsumer {

        private final ChannelInputStream inputStream;
        private final ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        private List<String> lines = Lists.newArrayList();

        public ChannelInputStreamNonBlockingLineConsumer(ChannelInputStream inputStream) {
            this.inputStream = inputStream;
        }

        public List<String> readAvailableLines() {
            int availableBytes = inputStream.available();
            if (availableBytes > 0) {
                for (int i = 0; i < availableBytes; i++) {
                    int readByte;
                    try {
                        readByte = inputStream.read();
                    } catch (IOException e) {
                        throw Throwables.propagate(e);
                    }
                    // should work for windows/linux/new macs
                    if (readByte == Ascii.LF) {
                        lines.add(new String(outputStream.toByteArray(), Charsets.UTF_8));
                        outputStream.reset();
                    } else {
                        outputStream.write(readByte);
                    }
                }
            }
            if (lines.isEmpty()) {
                return Collections.emptyList();
            } else {
                List<String> result = lines;
                lines = Lists.newArrayList();
                return result;
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
        public InputStream getInputStream() {
            return new ByteArrayInputStream(bytes);
        }
    }

    /**
     * {@link InMemoryDestFile} implementations that stores the output in a byte array.
     */
    private static class StringDestFile extends InMemoryDestFile {
        private final ByteArrayOutputStream outputStream = new ByteArrayOutputStream();

        @Override
        public OutputStream getOutputStream() {
            return outputStream;
        }

        public String getContent() {
            return new String(outputStream.toByteArray(), Charsets.UTF_8);
        }
    }

}
