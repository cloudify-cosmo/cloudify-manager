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

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.manager.config.ValidatorConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.utils.ResourceExtractor;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.util.Map;

/**
 * Validates cosmo TOSCA dsl.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public class Validator {

    private static final Logger LOGGER = LoggerFactory.getLogger(Validator.class);

    private static final String RUBY_RESOURCES_CLASS_LOADER_BEAN_NAME = "rubyResourcesClassLoader";
    private static final String SCRIPTS_RESOURCE_PATH = "scripts";
    private static final String RUOTE_GEMS_RESOURCE_PATH = "ruote-gems/gems";
    private static final String TEMPORARY_DIRECTORY_BEAN_NAME = "temporaryDirectory";

    public static void validateDSL(String dslPath) throws IOException {
        AnnotationConfigApplicationContext bootContext = registerTempDirectoryConfig();
        TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory =
                (TemporaryDirectoryConfig.TemporaryDirectory) bootContext.getBean("temporaryDirectory");
        AnnotationConfigApplicationContext mainContext =
                registerConfig(temporaryDirectory.get().toPath(), temporaryDirectory);
        RuoteWorkflow ruoteWorkflow = (RuoteWorkflow) mainContext.getBean("validateRuoteWorkflow");
        RuoteRuntime ruoteRuntime = (RuoteRuntime) mainContext.getBean("validateRuoteRuntime");
        try {
            final Map<String, Object> workitemFields = Maps.newHashMap();
            workitemFields.put("dsl", dslPath);
            final Object wfid = ruoteWorkflow.asyncExecute(workitemFields);
            ruoteRuntime.waitForWorkflow(wfid, 60);
        } finally {
            closeContext(mainContext);
            closeContext(bootContext);
        }
    }

    private static AnnotationConfigApplicationContext registerConfig(
            Path extractionPath,
            TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory) throws IOException {

        ResourceExtractor.extractResource(SCRIPTS_RESOURCE_PATH, extractionPath);
        ResourceExtractor.extractResource(RUOTE_GEMS_RESOURCE_PATH, extractionPath);
        URLClassLoader ruoteClassLoader = new URLClassLoader(new URL[] {
                extractionPath.toAbsolutePath().toUri().toURL() }, null);
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        context.getBeanFactory().registerSingleton(RUBY_RESOURCES_CLASS_LOADER_BEAN_NAME, ruoteClassLoader);
        context.getBeanFactory().registerSingleton(TEMPORARY_DIRECTORY_BEAN_NAME, temporaryDirectory);
        context.register(ValidatorConfig.class);
        context.refresh();
        return context;
    }

    private static AnnotationConfigApplicationContext registerTempDirectoryConfig() {
        AnnotationConfigApplicationContext contextForTempDir = new AnnotationConfigApplicationContext();
        contextForTempDir.register(TemporaryDirectoryConfig.class);
        contextForTempDir.refresh();
        return contextForTempDir;
    }

    private static void closeContext(AnnotationConfigApplicationContext context) throws IOException {
        if (context != null && context.isActive()) {
            LOGGER.debug("Closing spring application context : " + context);
            context.close();
        }
    }
}
