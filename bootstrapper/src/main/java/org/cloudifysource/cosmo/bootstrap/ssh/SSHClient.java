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

package org.cloudifysource.cosmo.bootstrap.ssh;

import com.google.common.base.Charsets;
import com.google.common.base.Joiner;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import net.schmizz.sshj.transport.verification.PromiscuousVerifier;
import net.schmizz.sshj.xfer.InMemorySourceFile;
import net.schmizz.sshj.xfer.LocalSourceFile;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.concurrent.ExecutionException;

/**
 * An ssh client implementation.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SSHClient implements AutoCloseable {

    private final Logger logger = LoggerFactory.getLogger(getClass());

    private final net.schmizz.sshj.SSHClient sshClient;
    private final SSHConnectionInfo connectionInfo;
    private final SessionCommandExecutionMonitor sessionCommandExecutionMonitor;

    public SSHClient(String host,
                     int port,
                     String userName,
                     String keyFile,
                     SessionCommandExecutionMonitor sessionCommandExecutionMonitor) {
        try {
            this.sshClient = new net.schmizz.sshj.SSHClient();
            sshClient.addHostKeyVerifier(new PromiscuousVerifier());
            sshClient.connect(host, port);
            sshClient.authPublickey(userName, keyFile);
            this.connectionInfo = new SSHConnectionInfo(host, port, userName);
            this.sessionCommandExecutionMonitor = sessionCommandExecutionMonitor;
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    /**
     * Create a file on the remote host with the given string as its content.
     *
     * @param parentRemotePath The directory to create the file in.
     * @param name The name of the file to create in 'parentRemotePath'
     * @param content The content of the file to create.
     */
    public void putString(String parentRemotePath, String name, String content) {
        put(parentRemotePath, name, new StringSourceFile(name, content));
    }

    private void put(String parentRemotePath, String name, LocalSourceFile localSourceFile) {
        try {
            execute("mkdir -p " + parentRemotePath).get();
            if (!parentRemotePath.endsWith("/")) {
                parentRemotePath += "/";
            }
            sshClient.newSCPFileTransfer().upload(localSourceFile, parentRemotePath + name);
        } catch (IOException | InterruptedException | ExecutionException  e) {
            throw Throwables.propagate(e);
        }
    }

    /**
     * Executes the given script at the remote host.
     * @param workingDirectory The working directory in which the script should be executed.
     * @param scriptPath A path to the script on the remote host.
     * @return A future whose value will be set to null upon sucessful execution and an exception will be set
     *  otherwise.
     */
    public ListenableFuture<?> executeScript(String workingDirectory, String scriptPath) {
        return executeScript(workingDirectory, scriptPath, null);
    }

    /**
     * Executes the given script at the remote host.
     * @param workingDirectory The working directory in which the script should be executed.
     * @param scriptPath A path to the script on the remote host.
     * @param lineConsumedListener An output listener for this execution.
     * @return A future whose value will be set to null upon sucessful execution and an exception will be set
     *  otherwise.
     */
    public ListenableFuture<?> executeScript(String workingDirectory, String scriptPath,
                                             LineConsumedListener lineConsumedListener) {
        List<String> commands = Lists.newLinkedList();
        commands.add("cd " + workingDirectory);
        commands.add("chmod +x " + scriptPath);
        commands.add(scriptPath);
        return execute(Joiner.on(';').join(commands), lineConsumedListener);
    }

    /**
     * Executes the given command at the remote host.
     * @param command The command to execute.
     * @return A future whose value will be set to null upon sucessful execution and an exception will be set
     *  otherwise.
     */
    public ListenableFuture<?> execute(String command) {
        return execute(command, null);
    }

    /**
     * Executes the given command at the remote host.
     * @param command The command to execute.
     * @param lineConsumedListener An output listener for this execution.
     * @return A future whose value will be set to null upon sucessful execution and an exception will be set
     *  otherwise.
     */
    public ListenableFuture<?> execute(String command, LineConsumedListener lineConsumedListener) {
        logger.debug("Excecuting command: [{}]", command);
        final SSHSessionCommandExecution sessionCommmand = new SSHSessionCommandExecution(sshClient, connectionInfo,
                command, lineConsumedListener);
        ListenableFuture<?> result = sessionCommandExecutionMonitor.addSessionCommand(sessionCommmand);
        Futures.addCallback(result, new FutureCallback<Object>() {
            @Override
            public void onFailure(Throwable t) {
                sessionCommmand.close();
            }
            @Override public void onSuccess(Object result) { }
        });
        return result;
    }

    /**
     * Closes the underlying components.
     */
    @Override
    public void close() {
        try {
            sshClient.close();
        } catch (IOException e) {
            logger.debug("Failed closing ssh client", e);
        }
    }

    /**
     * {@link net.schmizz.sshj.xfer.InMemorySourceFile} implementation that takes a {@link String} as its input.
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

}
