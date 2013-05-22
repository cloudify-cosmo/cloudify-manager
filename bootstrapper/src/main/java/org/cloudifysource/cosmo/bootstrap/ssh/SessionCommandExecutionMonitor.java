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
                        blockIfNoSessionCommandsAreAvailable();

                        // iterate all currently active session command. some will be read from, some will be removed
                        // and closed.
                        consumeCurrentlyAvailableOutput();

                        // don't want to to waste precious CPU
                        Thread.sleep(10);

                    }
                } catch (InterruptedException e) {
                    // We are outside the read loop. Interrupt is the machanism to stop this
                    // thread. Simply do nothing and end exection.
                }
            }

            private void blockIfNoSessionCommandsAreAvailable() throws InterruptedException {
                if (sessionCommands.isEmpty()) {
                    lock.lockInterruptibly();
                    try {
                        while (sessionCommands.isEmpty()) {
                            // wait for signal from addSessionCommand
                            notEmptyCondition.await();
                        }
                    } finally {
                        lock.unlock();
                    }
                }
            }

            private void consumeCurrentlyAvailableOutput() {
                for (Iterator<Map.Entry<SSHSessionCommandExecution, SettableFuture<?>>> iterator =
                             sessionCommands.entrySet().iterator();
                     iterator.hasNext();) {
                    Map.Entry<SSHSessionCommandExecution, SettableFuture<?>> entry = iterator.next();

                    SSHSessionCommandExecution sessionCommand = entry.getKey();
                    SettableFuture<?> future = entry.getValue();

                    if (sessionCommand.isOpen() && !future.isCancelled()) {
                        // session is active, check if socket has pending bytes to read.
                        try {
                            // readAvailableLines is where we actually read from the input stream
                            // and where we will fail if the connection is dead.
                            consumeOutput(sessionCommand);
                        } catch (Exception e) {
                            iterator.remove();
                            setFutureIfNeeded(sessionCommand, future, e);
                        }
                    } else {
                        // consume last lines (if any exist).
                        try {
                            consumeOutput(sessionCommand);
                        } catch (Exception e) {
                            // output lines may fail when reading output after
                            // the transport dies. if so, ignore.
                        }

                        iterator.remove();
                        setFutureIfNeeded(sessionCommand, future, null /* exception */);
                    }
                }
            }

            private void consumeOutput(SSHSessionCommandExecution sessionCommand) {
                for (String line : sessionCommand.readAvailableLines()) {
                    logger.debug("[{}] {}", sessionCommand.getConnectionInfo(), line);
                }
            }

            private void setFutureIfNeeded(SSHSessionCommandExecution sessionCommand,
                                           SettableFuture<?> future, Exception exception) {
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
