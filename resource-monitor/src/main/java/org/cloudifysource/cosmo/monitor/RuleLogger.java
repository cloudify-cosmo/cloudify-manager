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

package org.cloudifysource.cosmo.monitor;

import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.drools.spi.KnowledgeHelper;

/**
 * A utility method imported into a DRL file, used for logging.
 *
 * In the drl file add the following line:
 * import function org.cloudifysource.cosmo.monitor.RuleLogger.log;
 *
 * You can use the logger in the DRL "then" section by calling log with drools as the first parameter,
 * and the rest is the standard slf4j log syntax:
 * log(drools, "Hello {}", 123)
 *
 * The logger name would be the package name of the rule, and the logging level is debug.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class RuleLogger {

    /**
     * See http://blog.lunatech.com/2011/09/02/logging-debug-drools .
     */
    public static void log(final KnowledgeHelper drools, final String message,
                           final Object... parameters) {
        final String loggerName = drools.getRule().getPackageName();
        final Logger logger = LoggerFactory.getLogger(loggerName);
        if (logger.isDebugEnabled()) {
            logger.debug("[" + drools.getRule().getName() + "] " + message, parameters);
        }
    }
}
