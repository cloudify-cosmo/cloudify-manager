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

import com.google.common.base.Ascii;
import com.google.common.base.Charsets;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import net.schmizz.sshj.connection.ConnectionException;
import net.schmizz.sshj.connection.channel.ChannelInputStream;
import net.schmizz.sshj.connection.channel.direct.Session;
import net.schmizz.sshj.transport.TransportException;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Collections;
import java.util.List;

/**
 * Encapsulates an ongoing ssh execution.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SSHSessionCommandExecution implements AutoCloseable {

    private final Logger logger = LoggerFactory.getLogger(getClass());

    private final SSHConnectionInfo connectionInfo;
    private final LineConsumedListener lineConsumedListener;
    private final Session session;
    private final Session.Command sessionCommand;
    private final SessionCommandNonBlockingLineConsumer lineConsumer;

    public SSHSessionCommandExecution(net.schmizz.sshj.SSHClient sshClient,
                                      SSHConnectionInfo connectionInfo,
                                      String command,
                                      LineConsumedListener lineConsumedListener) {
        this.connectionInfo = connectionInfo;
        this.lineConsumedListener = lineConsumedListener;
        try {
            this.session = sshClient.startSession();
            this.session.allocateDefaultPTY();
            this.sessionCommand = session.exec(command);
            this.lineConsumer = new SessionCommandNonBlockingLineConsumer(sessionCommand);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    public boolean isOpen() {
        return sessionCommand.isOpen();
    }

    public SSHConnectionInfo getConnectionInfo() {
        return connectionInfo;
    }

    public List<String> readAvailableLines() {
        return lineConsumer.readAvailableLines();
    }

    public Integer getExitStatus() {
        return sessionCommand.getExitStatus();
    }

    @Override
    public void close() {
        // session command and session are the same instance.
        // so we invoke close on session only.
        try {
            session.close();
        } catch (ConnectionException | TransportException e) {
            throw Throwables.propagate(e);
        }
    }

    /**
     * Reads lines in a non blocking manner for the given {@link Session.Command}.
     */
    private class SessionCommandNonBlockingLineConsumer {

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
    private class ChannelInputStreamNonBlockingLineConsumer {

        private final byte[] buffer = new byte[4096];
        private final ChannelInputStream inputStream;
        private final ByteArrayOutputStream outputStream = new ByteArrayOutputStream();

        private List<String> lines = Lists.newArrayList();

        public ChannelInputStreamNonBlockingLineConsumer(ChannelInputStream inputStream) {
            this.inputStream = inputStream;
        }

        public List<String> readAvailableLines() {
            int availableBytes = inputStream.available();
            while (availableBytes > 0) {
                int bytesToRead = availableBytes <= buffer.length ? availableBytes : buffer.length;
                int bytesRead;
                try {
                    bytesRead = inputStream.read(buffer, 0, bytesToRead);
                    availableBytes -= bytesRead;
                } catch (IOException e) {
                    throw Throwables.propagate(e);
                }

                for (int i = 0; i < bytesRead; i++) {
                    int readByte = buffer[i];
                    // should work for windows/linux/new macs
                    if (readByte == Ascii.LF) {
                        String line = new String(outputStream.toByteArray(), Charsets.UTF_8);
                        lines.add(line);
                        if (lineConsumedListener != null) {
                            lineConsumedListener.onLineConsumed(getConnectionInfo(), line.trim());
                        }
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

}
