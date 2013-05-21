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

import org.cloudifysource.cosmo.bootstrap.AgentBootstrapSetup;
import org.hibernate.validator.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Creats a new {@link org.cloudifysource.cosmo.bootstrap.AgentBootstrapSetup}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class AgentBootstrapSetupConfig {

    @NotEmpty
    @Value("${cosmo.bootstrap.work-dir}")
    private String workDirectory;

    @NotEmpty
    @Value("${cosmo.bootstrap.cosmo-url}")
    private String cosmoUrl;

    @Value("${cosmo.bootstrap.java-url:}")
    private String javaUrl;

    @NotEmpty
    @Value("${cosmo.bootstrap.bootstrap-script-resource}")
    private String bootstrapScriptResource;

    @NotEmpty
    @Value("${cosmo.bootstrap.bootstrap-properties-resource}")
    private String bootstrapPropertiesResource;

    @Bean
    public AgentBootstrapSetup agentBootstrapSetup() {
        return new AgentBootstrapSetup(bootstrapScriptResource,
                                       workDirectory,
                                       bootstrapPropertiesResource,
                                       cosmoUrl,
                                       javaUrl);
    }

}
