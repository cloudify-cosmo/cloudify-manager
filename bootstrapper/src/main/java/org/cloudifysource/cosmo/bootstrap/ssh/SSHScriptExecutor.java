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
import com.google.common.base.Objects;
import com.google.common.base.Throwables;
import com.google.common.util.concurrent.AbstractFuture;
import com.google.common.util.concurrent.ListenableFuture;
import net.schmizz.sshj.SSHClient;
import net.schmizz.sshj.transport.verification.PromiscuousVerifier;
import net.schmizz.sshj.xfer.InMemorySourceFile;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * An ssh client implementation.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SSHScriptExecutor {

    private final Logger logger = LoggerFactory.getLogger(getClass());

    private final SSHConnectionInfo connectionInfo;

    public SSHScriptExecutor(String host,
                             int port,
                             String userName,
                             String keyFile) {
        this.connectionInfo = new SSHConnectionInfo(host, port, userName, keyFile);
    }

    private void writeFileOnRemoteHostFromStringContent(
            SSHClient sshClient, StringToCopyAsFile stringToCopyAsFile, SSHExecutionFuture executionFuture) {
        try {
            String parentRemotePath = stringToCopyAsFile.getParentRemotePath();
            String name = stringToCopyAsFile.getName();
            String content = stringToCopyAsFile.getContent();
            execute(sshClient, "mkdir -p " + parentRemotePath, Collections.<StringToCopyAsFile>emptyList(), null,
                    executionFuture);
            if (!parentRemotePath.endsWith("/")) {
                parentRemotePath += "/";
            }
            sshClient.newSCPFileTransfer().upload(new StringSourceFile(name, content), parentRemotePath + name);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    /**
     *
     * @param workingDirectory The working directory.
     * @param scriptPath The path of the script to execute.
     * @param stringsToCopyAsFiles String to write as files on the remote host before script execution.
     * @param lineConsumedListener A line cosumed listener.
     * @return
     */
    public ListenableFuture<?> executeScript(
            final String workingDirectory,
            final String scriptPath,
            final List<StringToCopyAsFile> stringsToCopyAsFiles,
            final LineConsumedListener lineConsumedListener) {

        final ExecutorService executorService = Executors.newSingleThreadExecutor();
        final SSHClient sshClient = new SSHClient();
        sshClient.addHostKeyVerifier(new PromiscuousVerifier());

        final SSHExecutionFuture executionFuture = new SSHExecutionFuture(executorService, sshClient);

        executorService.execute(new Runnable() {
            @Override
            public void run() {

                try {

                    String command = Joiner.on(';').join(
                            "cd " + workingDirectory,
                            "chmod +x " + scriptPath,
                            scriptPath
                    );
                    logger.debug("Excecuting command: [{}]", command);

                    sshClient.connect(connectionInfo.getHost(), connectionInfo.getPort());

                    sshClient.authPublickey(connectionInfo.getUserName(), connectionInfo.getKeyFile());
                    int exitStatus = execute(sshClient, command, stringsToCopyAsFiles, lineConsumedListener,
                            executionFuture);

                    if (!executionFuture.isCancelled()) {
                        if (exitStatus != 0) {
                            executionFuture.setException(new SSHExecutionException(exitStatus));
                        } else {
                            executionFuture.set(null);
                        }
                    }

                } catch (Throwable t) {
                    if (!executionFuture.isCancelled()) {
                        executionFuture.setException(t);
                    }
                }
            }
        });

        return executionFuture;
    }

    private int execute(
            SSHClient sshClient,
            String command,
            List<StringToCopyAsFile> stringsToCopyAsFiles,
            LineConsumedListener lineConsumedListener, SSHExecutionFuture executionFuture) {

        for (StringToCopyAsFile stringToCopyAsFile : stringsToCopyAsFiles) {
            writeFileOnRemoteHostFromStringContent(sshClient, stringToCopyAsFile, executionFuture);
        }

        logger.debug("Excecuting command: [{}]", command);
        final SSHSessionCommandExecution sessionCommmand = new SSHSessionCommandExecution(sshClient, connectionInfo,
                command, lineConsumedListener);

        while (sessionCommmand.isOpen() && !executionFuture.isCancelled()) {
            for (String line : sessionCommmand.readAvailableLines()) {
                logger.debug("[{}] {}", connectionInfo, line);
            }
        }

        return Objects.firstNonNull(sessionCommmand.getExitStatus(), -1);

    }

    /**
     * Intentionally inner class as it is highly coupled with the runnable above.
     */
    private class SSHExecutionFuture extends AbstractFuture<Object> {

        private final ExecutorService executorService;
        private final SSHClient sshClient;

        public SSHExecutionFuture(ExecutorService executorService, SSHClient sshClient) {
            this.executorService = executorService;
            this.sshClient = sshClient;
        }

        @Override
        public boolean cancel(boolean mayInterruptIfRunning) {
            // Do not cancel more than once.
            // state synchronization is handled by abstract class.
            if (!super.cancel(mayInterruptIfRunning)) {
                return false;
            }

            executorService.shutdownNow();
            try {
                // TODO BOOTSTRAP rethrow?
                sshClient.close();
            } catch (IOException e) {
                logger.debug("Failed closing ssh client.", e);
            }
            return true;
        }

        @Override
        protected boolean set(Object value) {
            executorService.shutdownNow();
            try {
                sshClient.close();
            } catch (IOException e) {
                return super.setException(e);
            }
            return super.set(value);
        }

        @Override
        protected boolean setException(Throwable throwable) {
            executorService.shutdownNow();
            try {
                sshClient.close();
            } catch (IOException e) {
                logger.debug("Failed closing ssh client.", e);
            }
            return super.setException(throwable);
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
