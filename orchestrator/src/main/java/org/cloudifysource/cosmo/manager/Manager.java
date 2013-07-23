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
 *******************************************************************************/

package org.cloudifysource.cosmo.manager;

import com.google.common.collect.Maps;
import org.apache.commons.io.FileUtils;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.manager.config.MainManagerConfig;
import org.cloudifysource.cosmo.manager.process.CeleryWorkerProcess;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/**
 * Starts several manager based components.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Manager {

    private Logger logger = LoggerFactory.getLogger(Manager.class);

    private static final String RUBY_RESOURCES_CLASS_LOADER_BEAN_NAME = "rubyResourcesClassLoader";
    private static final String SCRIPTS_RESOURCE_PATH = "scripts";
    private static final String RUOTE_GEMS_RESOURCE_PATH = "ruote-gems/gems";

    private Path extractionPath;

    private AnnotationConfigApplicationContext context;

    private RuoteWorkflow ruoteWorkflow;
    private RuoteRuntime ruoteRuntime;
    private CeleryWorkerProcess celeryWorkerProcess;

    public static void main(String[] args) throws Exception {

        Manager manager = null;
        try {
            manager = new Manager();
            manager.deployDSL("asd");
        } finally {
            if (manager != null) {
                manager.close();
            }
        }
    }

    private Manager() throws IOException {
        context = registerConfig();
        ruoteWorkflow = (RuoteWorkflow) context.getBean("defaultRuoteWorkflow");
        ruoteRuntime = (RuoteRuntime) context.getBean("ruoteRuntime");
        celeryWorkerProcess = (CeleryWorkerProcess) context.getBean("celeryWorkerProcess");
    }

    public void deployDSL(String dslPath) {

        final Map<String, Object> workitemFields = Maps.newHashMap();
        workitemFields.put("dsl", dslPath);

        final Object wfid = ruoteWorkflow.asyncExecute(workitemFields);
        ruoteRuntime.waitForWorkflow(wfid);
    }

    private AnnotationConfigApplicationContext registerConfig() throws IOException {
        extractionPath = Paths.get("extracted").toAbsolutePath();
        ResourceExtractor.extractResource(SCRIPTS_RESOURCE_PATH, extractionPath);
        ResourceExtractor.extractResource(RUOTE_GEMS_RESOURCE_PATH, extractionPath);
        URLClassLoader ruoteClassLoader = new URLClassLoader(new URL[] {
                extractionPath.toAbsolutePath().toUri().toURL() }, null);
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        context.getBeanFactory().registerSingleton(RUBY_RESOURCES_CLASS_LOADER_BEAN_NAME, ruoteClassLoader);
        context.register(MainManagerConfig.class);
        context.refresh();
        return context;
    }

    public void close() throws Exception {
        logger.debug("Closing [" + Manager.class.getName() +
                "] - deleting directory : " +
                extractionPath.toAbsolutePath());
        context.close();
        FileUtils.deleteDirectory(extractionPath.toFile());
    }
}
