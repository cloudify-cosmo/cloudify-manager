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

import com.beust.jcommander.Parameter;
import com.beust.jcommander.Parameters;
import com.beust.jcommander.validators.PositiveInteger;
import org.cloudifysource.cosmo.manager.cli.validator.FileExistValidator;

/**
 * Command line arguments passed to the ManagerBoot.
 *
 * @see {@link ManagerBoot}
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@Parameters(separators = "=")
public class Args {

    @Parameter(names = "-dsl",
               description = "Path to a TOSCA yaml describing the deployment.",
               validateWith = FileExistValidator.class, required = true)
    private String dslPath;

    @Parameter(names = "-timeout",
               description = "timeout for the deployment in seconds.",
               validateWith = PositiveInteger.class)
    private int timeout = 5 * 60; // defaults to 5 minutes.

    @Parameter(names = "--help", help = true, hidden = true)
    private boolean help;

    public boolean isHelp() {
        return help;
    }

    public String getDslPath() {
        return dslPath;
    }

    public int getTimeout() {
        return timeout;
    }
}
