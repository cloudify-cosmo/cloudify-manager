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

package org.cloudifysource.cosmo.bootstrap.config;

import com.google.common.base.Strings;
import org.hibernate.validator.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import java.util.Map;

/**
 * Creates a new {@link org.cloudifysource.cosmo.bootstrap.ssh.SSHBootstrapper}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class AgentSSHBootstrapperConfig extends SSHBootstrapperConfig {

    private static final String COSMO_ENV_JAVA_URL = "COSMO_ENV_JAVA_URL";
    private static final String COSMO_URL = "COSMO_URL";
    private static final String COSMO_WORK_DIRECTORY = "COSMO_WORK_DIRECTORY";

    @NotEmpty
    @Value("${cosmo.bootstrap.cosmo-url}")
    private String cosmoUrl;

    @Value("${cosmo.bootstrap.java-url:}")
    private String javaUrl;

    @Override
    protected void addEnviromentVariables(Map<String, String> environmentVariables) {
        super.addEnviromentVariables(environmentVariables);
        environmentVariables.put(COSMO_WORK_DIRECTORY, workDirectory);
        environmentVariables.put(COSMO_URL, cosmoUrl);
        if (!Strings.isNullOrEmpty(javaUrl)) {
            environmentVariables.put(COSMO_ENV_JAVA_URL, javaUrl);
        }
    }
}
