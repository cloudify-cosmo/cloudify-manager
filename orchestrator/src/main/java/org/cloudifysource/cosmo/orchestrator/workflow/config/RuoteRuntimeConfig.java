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

package org.cloudifysource.cosmo.orchestrator.workflow.config;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import com.google.common.base.Charsets;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.ruote.RuoteRadialVariable;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.tasks.TaskExecutor;
import org.cloudifysource.cosmo.tasks.config.TaskExecutorConfig;
import org.hibernate.validator.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.util.Map;

/**
 * Creates a new {@link org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
@PropertySource("org/cloudifysource/cosmo/manager/ruote/ruote.properties")
public class RuoteRuntimeConfig {

    @NotEmpty
    @Value("${cosmo.ruote.workflows:ruote/workflows.yaml}")
    private String workflows;

    @Inject
    private StateCache stateCache;

    @Inject
    private TaskExecutor taskExecutor;

    @Inject
    private URLClassLoader rubyResourcesClassLoader;

    @Bean
    public RuoteRuntime ruoteRuntime() throws IOException {
        Map<String, Object> runtimeProperties = Maps.newHashMap();
        runtimeProperties.put("state_cache", stateCache);
        runtimeProperties.put("executor", taskExecutor);

        final Map<String, Object> variables = Maps.newHashMap();
        variables.putAll(loadInitialWorkflows());

        return RuoteRuntime.createRuntime(runtimeProperties, variables, rubyResourcesClassLoader);
    }

    private static String getContent(String resource) throws IOException {
        final URL url = Resources.getResource(resource);
        return Resources.toString(url, Charsets.UTF_8);
    }

    private Map<String, RuoteRadialVariable> loadInitialWorkflows() throws IOException {
        ObjectMapper mapper = newObjectMapper();
        String workflowsMapping = getContent(workflows);
        Map<String, String> workflowsMappingMap = mapper.readValue(workflowsMapping,
                new TypeReference<Map<String, String>>() { });
        Map<String, RuoteRadialVariable> result = Maps.newHashMap();
        for (Map.Entry<String, String> entry : workflowsMappingMap.entrySet()) {
            String bindingName = entry.getKey();
            String workflowContent = getContent(entry.getValue());
            result.put(bindingName, new RuoteRadialVariable(workflowContent));
        }
        return result;
    }

    private static ObjectMapper newObjectMapper() {
        ObjectMapper mapper = new ObjectMapper(new YAMLFactory());
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        return mapper;
    }
}
