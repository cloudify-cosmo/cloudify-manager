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

import com.beust.jcommander.JCommander;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.manager.cli.Args;

/**
 * Boots up the manager with spring dependency injection and deploys the specified DSL.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
public class ManagerBoot {

    private static final Logger LOGGER = LoggerFactory.getLogger(ManagerBoot.class);

    private static Manager manager;

    public static void main(String[] args) throws Exception {

        Runtime.getRuntime().addShutdownHook(new Thread(new CleanupShutdownHook()));

        Args parsed = new Args();

        parseArgs(args, parsed);

        String dslPath = parsed.getDslPath();
        int timeout = parsed.getTimeout();

        if (parsed.isValidate()) {
            LOGGER.info(ManagerLogDescription.VALIDATING_DSL, dslPath);
            Validator.validateDSL(dslPath);
        } else {
            try {
                LOGGER.info(ManagerLogDescription.BOOTING_MANAGER);
                manager = new Manager();
                manager.init();
                LOGGER.info(ManagerLogDescription.DEPLOYING_DSL, dslPath);
                manager.deployDSL(dslPath, timeout);
            } finally {
                if (manager != null) {
                    manager.close();
                }
            }
        }
    }

    private static void parseArgs(String[] args, Args parsed) {
        try {
            JCommander commander = new JCommander(parsed, args);
            commander.setProgramName("");
            if (parsed.isHelp()) {
                commander.usage();
                System.exit(0);
            }
        } catch (Exception e) {
            System.err.println(e.getMessage());
            System.exit(1);
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
