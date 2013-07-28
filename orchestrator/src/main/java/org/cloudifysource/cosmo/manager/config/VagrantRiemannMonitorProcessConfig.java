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

package org.cloudifysource.cosmo.manager.config;

import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.tasks.ProcessOutputLogger;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PreDestroy;
import java.io.IOException;

/**
 * Configuration for shutting down the riemann monitor process.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class VagrantRiemannMonitorProcessConfig {

    private Logger logger = LoggerFactory.getLogger(VagrantRiemannMonitorProcessConfig.class);

    @PreDestroy
    public void killMonitor() throws IOException, InterruptedException {

        logger.debug("Killing vagrant monitor process");

        int retryCount = 0;
        // workaround signaling issue with vagrant-riemann monitor.
        // sometimes, the kill signal gets caught by an underlying layer and
        // never reaches our signal handler.

        Process process = null;
        while (retryCount < 3) {
            process = runProcess();
            process.waitFor();
            Thread.sleep(100);
            if (!isProcessAlive(process)) {
                break;
            }
            retryCount++;
            Thread.sleep(5000);
        }
        if (process != null && isProcessAlive(process)) {
            throw new IllegalStateException("Failed closing vagrant monitor process");
        }
    }

    private Process runProcess() {
        String[] command = {"/bin/sh", "-c", "kill $(ps aux | grep '[m]onitor.py' | awk '{print $2}')"};
        ProcessBuilder builder = new ProcessBuilder();
        builder.command(command);
        ProcessOutputLogger processOutputLogger = new ProcessOutputLogger(builder, logger);
        return processOutputLogger.getProcess();
    }

    private boolean isProcessAlive(Process process) {
        try {
            process.exitValue();
            return false;
        } catch (IllegalThreadStateException e) {
            return true;
        }
    }

}
