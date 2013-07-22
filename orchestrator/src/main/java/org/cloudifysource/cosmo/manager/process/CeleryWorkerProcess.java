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

import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.manager.JarPackageExtractor;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.net.URL;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Arrays;

/**
 * Executes an external celery worker.
 * The process is closed with {@link #close()}
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class CeleryWorkerProcess implements AutoCloseable {

    private String celeryPidFileName;
    private static final String CELERY_LOG_LEVEL = "debug";
    protected final Logger logger = LoggerFactory.getLogger(this.getClass());
    private ProcessOutputLogger processOutputLogger;
    private String workingDir;

    public CeleryWorkerProcess(final String app, final String workingDir) {
        long currentTime = System.currentTimeMillis();
        this.celeryPidFileName = "celery_worker.pid" + currentTime;
        this.workingDir = workingDir;

        String[] command = new String[] {"celery",
                                         "worker",
                                         "--events",
                                         "--loglevel=" + CELERY_LOG_LEVEL,
                                         "--app=" + app,
                                         "--hostname=cloudify.management",
                                         "--purge", //for testing only
                                         "--pidfile=" + celeryPidFileName,
                                         "--include=" + buildCeleryIncludes(),
                                         "--queues=celery,cloudify.management"
        };
        logger.debug("Starting celery worker with command : " + Arrays.toString(command));
        runProcess(command);
        try {

            // we need to wait for the worker to actually be running.
            // otherwise we are sending the task prior to the existing of a worker.
            // this is no good.
            // TODO elip - think of a way to check that the worker is up.
            // TODO this could also benefit us in production.

            Thread.sleep(5000);

        } catch (InterruptedException e) {
            throw Throwables.propagate(e);
        }
    }

    private String buildCeleryIncludes() {
        final StringBuilder celeryIncludesBuilder = new StringBuilder();
        try {
            final Path root = getAppDirectory().toPath();
            Files.walkFileTree(root, new SimpleFileVisitor<Path>() {
                @Override
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    String fileName = file.getFileName().toString();
                    if (fileName.equals("tasks.py")) {
                        String relativeFileName = file.subpath(root.getNameCount(), file.getNameCount()).toString();
                        String moduleName = relativeFileName
                                .substring(0, relativeFileName.length() - ".py".length())
                                .replace(File.separatorChar, '.');
                        celeryIncludesBuilder.append(moduleName).append(",");
                    }
                    return FileVisitResult.CONTINUE;
                }

                @Override
                public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                    String dirName = dir.getFileName().toString();
                    String parentDirName = dir.getParent().getFileName().toString();
                    final boolean isDirNamedCosmo = dirName.equals("cosmo");
                    final boolean isParentDirNamedRemote = parentDirName.equals("remote");
                    return (isDirNamedCosmo && isParentDirNamedRemote) ? FileVisitResult.SKIP_SUBTREE :
                                                                         FileVisitResult.CONTINUE;
                }
            });
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
        if (celeryIncludesBuilder.length() > 0) {
            // remove last comma
            celeryIncludesBuilder.setLength(celeryIncludesBuilder.length() - 1);
        }
        return celeryIncludesBuilder.toString();
    }

    private Process runProcess(String[] command) {
        ProcessBuilder pb = new ProcessBuilder();

        // copy the app to the working dir
        Path appExtractionPath = Paths.get(getWorkingDir());
        try {
            JarPackageExtractor.extractPackage("celery/app", appExtractionPath, Resources.getResource("celery/app"));
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }

        pb.directory(new File(getWorkingDir()));
        pb.command(Lists.newArrayList(command));
        processOutputLogger = new ProcessOutputLogger(pb, logger);
        return processOutputLogger.getProcess();
    }

    private File getAppDirectory() {
        URL resource = Resources.getResource("celery/app");
        String path = resource.getPath();
        return new File(path);
    }

    private static boolean isWindows() {
        return System.getProperty("os.name").startsWith("Windows");
    }

    public String getWorkingDir() {
        return this.workingDir;
    }

    @Override
    public void close() throws Exception {
        processOutputLogger.close();

        final int pid = getPid();
        final String cmd = "taskkill /F /PID " + pid;

        Process p;
        logger.debug("Killing celery worker");
        if (isWindows()) {
            p = runProcess(new String[] {"cmd", "/c", cmd});
        } else {
            p = runProcess(new String [] {"kill", "-TERM", "" + pid});
        }
        int exitCode = p.waitFor();
        if (exitCode != 0) {
            throw new IllegalStateException("Failed to close celery worker process");
        }

        File celeryPid = new File(getWorkingDir(), celeryPidFileName);
        boolean deleted = celeryPid.delete();
        if (!deleted) {
            celeryPid.deleteOnExit();
        }
    }

    /**
     * @return celery worker process id.
     */
    private int getPid() {
        File pidFile = new File(getAppDirectory(), celeryPidFileName);
        try {
            BufferedReader in = new BufferedReader(new FileReader(pidFile));
            return Integer.valueOf(in.readLine());
        } catch (IOException ex) {
            throw Throwables.propagate(ex);
        }
    }
}
