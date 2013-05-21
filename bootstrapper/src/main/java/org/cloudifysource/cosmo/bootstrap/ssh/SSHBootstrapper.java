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

import com.google.common.base.Charsets;
import com.google.common.base.Strings;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;
import com.google.common.io.Resources;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.Bootstrapper;

import java.io.IOException;
import java.net.URL;
import java.util.Map;

/**
 * An SSH based {@link Bootstrapper}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SSHBootstrapper implements Bootstrapper {

    private static final String SCRIPT_NAME = "bootstrap.sh";
    private static final String ENV_SCRIPT_NAME = "bootstrap-env.sh";
    private static final String BOOTSTRAP_PROPERTIES = "bootstrap.properties";

    private final SSHClient sshClient;
    private final String workDirectory;
    private final String scriptResourceLocation;
    private final Map<String, String> scriptEnvironment;
    private final String propertiesResourceLocation;
    private final LineConsumedListener lineConsumedListener;

    public SSHBootstrapper(SSHClient sshClient,
                           String workDirectory,
                           String scriptResourceLocation,
                           Map<String, String> scriptEnvironment,
                           String propertiesResourceLocation,
                           LineConsumedListener lineConsumedListener) {
        this.sshClient = sshClient;
        this.workDirectory = workDirectory;
        this.scriptResourceLocation = scriptResourceLocation;
        this.scriptEnvironment = scriptEnvironment;
        this.propertiesResourceLocation = propertiesResourceLocation;
        this.lineConsumedListener = lineConsumedListener;
    }

    public String getPropertiesResourceLocation() {
        return propertiesResourceLocation;
    }

    public Map<String, String> getScriptEnvironment() {
        return ImmutableMap.copyOf(scriptEnvironment);
    }

    @Override
    public ListenableFuture<?> bootstrap() {
        try {

            // copy script to remote host
            URL url = Resources.getResource(scriptResourceLocation);
            String bootstrapScript = Resources.toString(url, Charsets.UTF_8);
            sshClient.putString(workDirectory, SCRIPT_NAME, bootstrapScript);

            // copy env script to remote host
            if (!scriptEnvironment.isEmpty()) {
                sshClient.putString(workDirectory, ENV_SCRIPT_NAME, ScriptUtils.toEnvScript(scriptEnvironment));
            }

            // copy properties file to remote host
            if (!Strings.isNullOrEmpty(propertiesResourceLocation)) {
                url = Resources.getResource(propertiesResourceLocation);
                String boostrapProperties = Resources.toString(url, Charsets.UTF_8);
                sshClient.putString(workDirectory, BOOTSTRAP_PROPERTIES, boostrapProperties);
            }

            // execute script
            return sshClient.executeScript(workDirectory, workDirectory + SCRIPT_NAME, lineConsumedListener);

        } catch (IOException e) {
            throw Throwables.propagate(e);
        }

    }

}
