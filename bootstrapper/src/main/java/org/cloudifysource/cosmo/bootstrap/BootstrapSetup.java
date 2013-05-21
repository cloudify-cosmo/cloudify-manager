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

package org.cloudifysource.cosmo.bootstrap;

import com.google.common.base.Optional;
import com.google.common.base.Strings;
import org.cloudifysource.cosmo.bootstrap.ssh.LineConsumedListener;

import java.util.Collections;
import java.util.Map;

/**
 * Generel boostrapping setup.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class BootstrapSetup {

    private final String scriptResourceLocation;
    private final String workDirectory;
    private final String propertiesResourceLocation;

    public BootstrapSetup(String scriptResourceLocation, String workDirectory,
                          String propertiesResourceLocation) {
        this.scriptResourceLocation = scriptResourceLocation;
        this.workDirectory = workDirectory;
        this.propertiesResourceLocation = propertiesResourceLocation;
    }

    /* This has to be outside so we know where to copy files. the rest should reside in env or properties. */

    /**
     * @return The working directory to execute the bootstrap script in.
     */
    public String getWorkDirectory() {
        return workDirectory;
    }

    /**
     * @return A resource path to the script to execute.
     */
    public String getScriptResourceLocation() {
        return scriptResourceLocation;
    }

    /**
     * @return The enviroment in which the bootstrap script should be executed with.
     */
    public Map<String, String> getScriptEnvironment() {
        return Collections.emptyMap();
    }

    /**
     * @return A resource path to a properties files which may be used by the bootstrapped process.
     * An empty string denotes no properties file should be used.
     */
    public Optional<String> getPropertiesResourceLocation() {
        if (Strings.isNullOrEmpty(propertiesResourceLocation)) {
            return Optional.absent();
        }
        return Optional.of(propertiesResourceLocation);
    }

    /**
     * @return An optional {@link LineConsumedListener} if this setup wishes to listen to bootstrap script
     * output.
     */
    public Optional<LineConsumedListener> getLinedLineConsumedListener() {
        return Optional.absent();
    }

}
