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

package org.cloudifysource.cosmo.manager.config;

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.IOException;
import java.net.URLClassLoader;
import java.util.Map;

/**
 * Creates a new {@link org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime} which is used only in the
 * dsl validation path.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
@Configuration
public class ValidateRuoteRuntimeConfig {

    @Autowired(required = false)
    private URLClassLoader rubyResourcesClassLoader;

    @Bean
    public RuoteRuntime validateRuoteRuntime() throws IOException {
        Map<String, Object> runtimeProperties = Maps.newHashMap();
        final Map<String, Object> variables = Maps.newHashMap();

        return RuoteRuntime.createRuntime(runtimeProperties, variables, rubyResourcesClassLoader);
    }

}
