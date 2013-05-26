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
import com.google.common.base.Joiner;
import com.google.common.base.Strings;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;
import com.google.common.io.Resources;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.Bootstrapper;

import java.io.IOException;
import java.net.URL;
import java.util.List;
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

    private final SSHScriptExecutor sshClient;
    private final String workDirectory;
    private final String scriptResourceLocation;
    private final Map<String, String> scriptEnvironment;
    private final String propertiesResourceLocation;

    private LineConsumedListener lineConsumedListener;

    public SSHBootstrapper(SSHScriptExecutor sshClient,
                           String workDirectory,
                           String scriptResourceLocation,
                           Map<String, String> scriptEnvironment,
                           String propertiesResourceLocation) {
        this.sshClient = sshClient;
        this.workDirectory = workDirectory;
        this.scriptResourceLocation = scriptResourceLocation;
        this.scriptEnvironment = scriptEnvironment;
        this.propertiesResourceLocation = propertiesResourceLocation;
    }

    public String getPropertiesResourceLocation() {
        return propertiesResourceLocation;
    }

    public void setLineConsumedListener(LineConsumedListener lineConsumedListener) {
        this.lineConsumedListener = lineConsumedListener;
    }

    public Map<String, String> getScriptEnvironment() {
        return ImmutableMap.copyOf(scriptEnvironment);
    }

    @Override
    public ListenableFuture<?> bootstrap() {
        try {

            List<StringToCopyAsFile> stringsToCopyAsFiles = Lists.newLinkedList();

            // copy script to remote host
            URL url = Resources.getResource(scriptResourceLocation);
            String bootstrapScript = Resources.toString(url, Charsets.UTF_8);
            stringsToCopyAsFiles.add(
                    new StringToCopyAsFile(workDirectory, SCRIPT_NAME, bootstrapScript));

            // copy env script to remote host
            // The script enviroment will be copied to the remote host and will reside in the work directory.
            // Its name will be bootstrap-env.sh and script may export its properties and use them in the scrxipt
            // using something like 'source bootstrap-env.sh'
            if (!scriptEnvironment.isEmpty()) {
                StringBuilder result = new StringBuilder("export ");
                String envScriptContext = Joiner.on("\nexport ")
                        .withKeyValueSeparator("=")
                        .appendTo(result, scriptEnvironment)
                        .toString();
                stringsToCopyAsFiles.add(
                        new StringToCopyAsFile(workDirectory, ENV_SCRIPT_NAME, envScriptContext));
            }

            // copy properties file to remote host
            // The properties file is optional and might be used when bootstrapping
            // spring based components (i.e. @PropertySource)/
            // The remote file will reside in the work directory. Its name will be
            // bootstrap.properties
            if (!Strings.isNullOrEmpty(propertiesResourceLocation)) {
                url = Resources.getResource(propertiesResourceLocation);
                String boostrapProperties = Resources.toString(url, Charsets.UTF_8);
                stringsToCopyAsFiles.add(
                        new StringToCopyAsFile(workDirectory, BOOTSTRAP_PROPERTIES,
                                boostrapProperties));
            }

            // execute script
            return sshClient.executeScript(
                    workDirectory,
                    workDirectory + SCRIPT_NAME,
                    stringsToCopyAsFiles,
                    lineConsumedListener);

        } catch (IOException e) {
            throw Throwables.propagate(e);
        }

    }

}
