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

import com.google.common.base.Objects;
import com.google.common.collect.Maps;
import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.SettableFuture;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Monitors SSH session commands and consumes their output.
 * When a session command ends, its future will be set to null if it ended succesfully
 * or an exception will be set on it if the script returned a non zero exist status or some exception occured during
 * execution.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SessionCommandExecutionMonitor implements AutoCloseable {

    private static final AtomicInteger ID = new AtomicInteger(1);

    private final Logger logger = LoggerFactory.getLogger(getClass());

    private final Lock lock = new ReentrantLock();
    private final Condition notEmptyCondition = lock.newCondition();

    private final ExecutorService executorService;
    private final ConcurrentMap<SSHSessionCommandExecution, SettableFuture<?>> sessionCommands;

    public SessionCommandExecutionMonitor() {
        sessionCommands = Maps.newConcurrentMap();
        executorService = Executors.newSingleThreadExecutor();
        executorService.submit(new Runnable() {
            @Override
            public void run() {
                Thread.currentThread().setName("command-execution-monitor" + ID.getAndIncrement());
                try {
                    // break on interrupt
                    while (!Thread.currentThread().isInterrupted()) {

                        // don't busy loop for nothing, only work when there is work to be done.
                        if (sessionCommands.isEmpty()) {
                            lock.lock();
                            try {
                                while (sessionCommands.isEmpty()) {
                                    // wait for signal from addSessionCommand
                                    notEmptyCondition.await();
                                }
                            } finally {
                                lock.unlock();
                            }
                        }

                        // iterate all currently active session command. some will be read from, some will be removed
                        // and closed.
                        for (Iterator<Map.Entry<SSHSessionCommandExecution, SettableFuture<?>>> iterator =
                                     sessionCommands.entrySet().iterator();
                             iterator.hasNext();) {

                            Map.Entry<SSHSessionCommandExecution, SettableFuture<?>> entry = iterator.next();
                            SSHSessionCommandExecution sessionCommand = entry.getKey();
                            SettableFuture<?> future = entry.getValue();

                            // session command has ended, remove from iterator, close session and update
                            // listenable future
                            if (!sessionCommand.isOpen() || future.isCancelled()) {
                                closeSessionCommand(iterator, sessionCommand, future, null /* exception */);
                                // consume last lines (if any exist).
                                outputLines(sessionCommand);
                                continue;
                            }

                            // session is active, check if socket has pending bytes to read.
                            try {
                                // readAvailableLines is where we actually read from the input stream
                                // and where we will fail if the connection is dead.
                                outputLines(sessionCommand);
                            } catch (Exception e) {
                                closeSessionCommand(iterator, sessionCommand, future, e);
                                continue;
                            }
                        }

                        // don't want to to waste precious CPU
                        Thread.sleep(10);
                    }
                } catch (InterruptedException e) {
                    return;
                }
            }

            private void outputLines(SSHSessionCommandExecution sessionCommand) {
                for (String line : sessionCommand.readAvailableLines()) {
                    logger.debug("[{}] {}", sessionCommand.getConnectionInfo(), line);
                }
            }

            private void closeSessionCommand(
                    Iterator<Map.Entry<SSHSessionCommandExecution, SettableFuture<?>>> iterator,
                    SSHSessionCommandExecution sessionCommand,
                    SettableFuture<?> future, Exception exception) {
                iterator.remove();
                if (future.isCancelled()) {
                    return;
                }

                if (exception != null) {
                    future.setException(exception);
                } else {
                    int exitStatus = Objects.firstNonNull(sessionCommand.getExitStatus(), -1);
                    if (exitStatus != 0) {
                        future.setException(new SSHExecutionException(exitStatus));
                    } else {
                        future.set(null);
                    }
                }
            }
        });
    }

    /**
     * @param sessionCommand An SSH session command to monitor.
     * @return a {@link com.google.common.util.concurrent.ListenableFuture} that will be set to null
     *         when the script execution completes succesfully or an exception will be set on it otherwise.
     */
    public ListenableFuture<?> addSessionCommand(SSHSessionCommandExecution sessionCommand) {
        lock.lock();
        try {
            SettableFuture<?> result = SettableFuture.create();
            sessionCommands.put(sessionCommand, result);
            // signal reader thread.
            notEmptyCondition.signal();
            return result;
        } finally {
            lock.unlock();
        }
    }

    public void close() {
        executorService.shutdownNow();
    }

}
