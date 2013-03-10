/*****************************************************************************
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

import com.google.common.base.Ascii;
import com.google.common.base.Charsets;
import com.google.common.base.Joiner;
import com.google.common.base.Objects;
import com.google.common.base.Optional;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import net.schmizz.sshj.SSHClient;
import net.schmizz.sshj.connection.channel.ChannelInputStream;
import net.schmizz.sshj.connection.channel.direct.Session;
import net.schmizz.sshj.sftp.SFTPClient;
import net.schmizz.sshj.transport.verification.PromiscuousVerifier;
import net.schmizz.sshj.xfer.FileSystemFile;
import net.schmizz.sshj.xfer.InMemoryDestFile;
import net.schmizz.sshj.xfer.InMemorySourceFile;
import net.schmizz.sshj.xfer.LocalSourceFile;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Helper class to perform basic file operations on a remote machine using ssh.
 *
 * @author Dank Kilman
 * @since 0.1
 */
public class AgentSSHClient {

    private static final Logger LOG = LoggerFactory.getLogger(AgentSSHClient.class);

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

    public void putFile(String parentRemotePath, String name, File sourcePath) {
        put(parentRemotePath, name, new FileSystemFile(sourcePath));
    }

    public void putString(String parentRemotePath, String name, String content) {
        put(parentRemotePath, name, new StringSourceFile(name, content));
    }

    // TODO SSH refactor: parent extraction logic to one place
    private void put(String parentRemotePath, String name, LocalSourceFile localSourceFile) {
        try {
            sftpClient.mkdirs(parentRemotePath);
            if (!parentRemotePath.endsWith("/")) {
                parentRemotePath += "/";
            }
            sftpClient.put(localSourceFile, parentRemotePath + name);
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

    // TODO SSH handle file not found vs other io exceptions
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
                StringBuilder export = new StringBuilder();
                export.append("export ").append(envVar.getKey()).append("=").append(envVar.getValue());
                commands.add(export.toString());
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

    /**
     * {@link net.schmizz.sshj.xfer.InMemoryDestFile} implementations that stores the output in a byte array.
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
