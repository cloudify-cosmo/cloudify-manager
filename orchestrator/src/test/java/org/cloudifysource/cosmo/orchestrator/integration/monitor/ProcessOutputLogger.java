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


package org.cloudifysource.cosmo.orchestrator.integration.monitor;

import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.logging.Logger;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Pipes process output to the logger provided during instantiation using
 * a dedicated thread.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class ProcessOutputLogger implements Runnable {

    private static final AtomicInteger ID = new AtomicInteger();

    private final Logger logger;
    private final BufferedReader processOutputReader;
    private final Process process;
    private final Thread thread;

    public Process getProcess() {
        return process;
    }

    public ProcessOutputLogger(ProcessBuilder processBuilder, Logger logger) {
        this.logger = logger;
        processBuilder.redirectErrorStream(true);
        try {
            this.process = processBuilder.start();
            InputStream processOutput = process.getInputStream();
            this.processOutputReader = new BufferedReader(new InputStreamReader(processOutput));
            this.thread = new Thread(this);
            this.thread.setDaemon(true);
            this.thread.setName("ProcessOutputLogger-" + ID.getAndIncrement());
            this.thread.start();
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    @Override
    public void run() {
        try {
            String line = processOutputReader.readLine();
            while (!Thread.interrupted() && line != null) {
                logger.debug(line);
                Thread.sleep(10);
                line = processOutputReader.readLine();
            }
        } catch (IOException e) {

        } catch (InterruptedException e) {
            // signal to stop
        }
    }

    public void close() {
        thread.interrupt();
    }

}
