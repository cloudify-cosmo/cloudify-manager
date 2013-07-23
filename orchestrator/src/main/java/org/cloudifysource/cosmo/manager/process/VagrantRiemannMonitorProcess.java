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

package org.cloudifysource.cosmo.manager.process;

import com.google.common.base.Charsets;
import com.google.common.collect.Lists;
import com.google.common.io.Files;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.Arrays;

/**
 * Starts a vagrant-riemann monitor process.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class VagrantRiemannMonitorProcess implements AutoCloseable {

    protected final Logger logger = LoggerFactory.getLogger(this.getClass());
    private final String pidFileName;
    private final File workDir;
    private ProcessOutputLogger processOutputLogger;
    private Process process;

    public VagrantRiemannMonitorProcess(String[] command, String pidFileName, File workDir) {
        this.pidFileName = pidFileName;
        this.workDir = workDir;
        logger.debug("Starting vagrant monitor with command : " + Arrays.toString(command));
        this.process = runProcess(workDir, command);
    }

    @Override
    public void close() throws Exception {
        processOutputLogger.close();

        logger.debug("Killing vagrant monitor process");

        int retryCount = 0;
        // workaround signaling issue with vagrant-riemann monitor.
        // sometimes, the kill signal gets caught by an underlying layer and
        // never reaches our signal handler.
        while (retryCount < 3) {
            runProcess(workDir, buildKillCmd()).waitFor();
            Thread.sleep(100);
            if (!isProcessAlive()) {
                break;
            }
            retryCount++;
            Thread.sleep(5000);
        }
        if (isProcessAlive()) {
            throw new IllegalStateException("Failed closing vagrant monitor process");
        }

        File pidFile = getPidFile();
        boolean deleted = pidFile.delete();
        if (!deleted) {
            pidFile.deleteOnExit();
        }
    }

    private Process runProcess(File workDir, String[] command) {
        ProcessBuilder pb = new ProcessBuilder();
        pb.directory(workDir);
        pb.command(Lists.newArrayList(command));
        processOutputLogger = new ProcessOutputLogger(pb, logger);
        return processOutputLogger.getProcess();
    }

    private String[] buildKillCmd() throws IOException {
        final int pid = getPid();
        final String[] windowsKillCmd = {"cmd", "/c", "taskkill /F /PID " + pid };
        final String[] linuxKillCmd = {"kill", "-TERM", "" + pid};
        return isWindows() ? windowsKillCmd : linuxKillCmd;
    }

    private File getPidFile() {
        return new File(workDir, pidFileName);
    }

    private int getPid() throws IOException {
        return Integer.parseInt(Files.readFirstLine(getPidFile(), Charsets.UTF_8));
    }

    private static boolean isWindows() {
        return System.getProperty("os.name").startsWith("Windows");
    }

    private boolean isProcessAlive() {
        try {
            process.exitValue();
            return false;
        } catch (IllegalThreadStateException e) {
            return true;
        }
    }
}
