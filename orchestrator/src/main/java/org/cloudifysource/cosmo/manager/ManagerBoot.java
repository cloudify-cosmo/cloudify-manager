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

package org.cloudifysource.cosmo.manager;

import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.File;
import java.nio.file.NoSuchFileException;

/**
 * Boots up the manager with spring dependency injection and deploys the specified DSL.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
public class ManagerBoot {

    private static final Logger LOGGER = LoggerFactory.getLogger(ManagerBoot.class);

    private static final long TIMEOUT_IN_SECONDS = 5 * 60; // 5 minutes.

    private static Manager manager;

    public static void main(String[] args) throws Exception {

        Runtime.getRuntime().addShutdownHook(new Thread(new CleanupShutdownHook()));

        if (args.length != 1) {
            throw new IllegalArgumentException("Invalid number of arguments");
        }
        String dslPath = args[0];
        File dsl = new File(dslPath);
        if (!dsl.exists()) {
            throw new NoSuchFileException("Could not find file : " + dsl.getAbsolutePath());
        }

        try {
            LOGGER.info(ManagerLogDescription.BOOTING_MANAGER);
            manager = new Manager();
            LOGGER.info(ManagerLogDescription.DEPLOYING_DSL, dslPath);
            manager.deployDSL(dslPath, TIMEOUT_IN_SECONDS);
        } finally {
            if (manager != null) {
                manager.close();
            }
        }
    }

    /**
     * Cleanup thread to close the manager in case the user hits ctrl+c from the command line.
     */
    private static class CleanupShutdownHook implements Runnable {

        @Override
        public void run() {
            LOGGER.debug("Executing cleanup shutdown hook");
            if (manager != null && !manager.isClosed()) {
                try {
                    LOGGER.debug("Closing manager");
                    manager.close();
                } catch (Exception e) {
                    LOGGER.warn(ManagerLogDescription.FAILED_SHUTTING_DOWN_MANAGER, e.getMessage());
                }
            }
        }
    }

}
