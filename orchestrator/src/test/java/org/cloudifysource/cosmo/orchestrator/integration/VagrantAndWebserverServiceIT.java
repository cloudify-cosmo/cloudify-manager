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

package org.cloudifysource.cosmo.orchestrator.integration;

import com.google.common.base.Charsets;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.manager.config.JettyFileServerForPluginsConfig;
import org.cloudifysource.cosmo.manager.dsl.DSLImporter;
import org.cloudifysource.cosmo.manager.dsl.config.JettyDSLImporterConfig;
import org.cloudifysource.cosmo.monitor.RiemannEventsLogger;
import org.cloudifysource.cosmo.monitor.config.RiemannEventsLoggerConfig;
import org.cloudifysource.cosmo.monitor.config.StateCacheFeederConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.orchestrator.workflow.config.DefaultRuoteWorkflowConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.tasks.config.CeleryWorkerProcessConfig;
import org.cloudifysource.cosmo.tasks.config.EventHandlerConfig;
import org.cloudifysource.cosmo.tasks.config.JythonProxyConfig;
import org.cloudifysource.cosmo.tasks.config.TaskExecutorConfig;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.robobninjas.riemann.spring.RiemannTestConfiguration;
import org.robobninjas.riemann.spring.server.RiemannProcess;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URL;
import java.util.Map;

/**
 * Test requirements:
 *
 * Python packages: celery, paramiko & python-vagrant.
 * Running rabbitmq server.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@ContextConfiguration(classes = { VagrantAndWebserverServiceIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class VagrantAndWebserverServiceIT extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @Import({
            TemporaryDirectoryConfig.class,
            JettyFileServerForPluginsConfig.class,
            CeleryWorkerProcessConfig.class,
            StateCacheConfig.class,
            StateCacheFeederConfig.class,
            RiemannTestConfiguration.class,
            DefaultRuoteWorkflowConfig.class,
            RuoteRuntimeConfig.class,
            TaskExecutorConfig.class,
            EventHandlerConfig.class,
            JythonProxyConfig.class,
            JettyDSLImporterConfig.class,
            RiemannEventsLoggerConfig.class

    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private DSLImporter dslImporter;

    @Inject
    private RuoteRuntime ruoteRuntime;

    @Inject
    private RuoteWorkflow ruoteWorkflow;

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @Value("${riemann.server.config-resource}")
    private String riemannConfigResourcePath;

    @Inject
    private RiemannProcess riemannProcess;

    @Inject
    private JettyFileServerForPluginsConfig jettyFileServerForPluginsConfig;

    @Inject
    private RiemannEventsLogger riemannEventsLogger;

    @Test(timeOut = 60000 * 5, groups = "vagrant", enabled = false)
    public void testWithVagrantHostProvisionerAndSimpleWebServerInstaller() throws IOException {
        test("org/cloudifysource/cosmo/dsl/integration_phase1/integration-phase1.yaml");
    }

    @Test(groups = "vagrant", enabled = true)
    public void testWithVagrantHostProvisionerAndRemoteCeleryWorker() throws IOException {
        test("org/cloudifysource/cosmo/dsl/integration_phase3/integration-phase3.yaml");
    }

    @Test(groups = "vagrant", enabled = true)
    public void testPhase4() throws IOException {
        test("org/cloudifysource/cosmo/dsl/integration_phase4/integration-phase4.yaml");
    }


    private void test(String dslPath) throws IOException {

        String dslLocation = dslImporter.importDSL(dslPath);

        final Map<String, Object> workitemFields = Maps.newHashMap();
        workitemFields.put("dsl", dslLocation);
        workitemFields.put("riemann_pid", String.valueOf(riemannProcess.getPid()));
        workitemFields.put("riemann_config_path", Resources.getResource(riemannConfigResourcePath).getPath());
        workitemFields.put("riemann_config_template", readRiemannConfigTemplate());

        final Object wfid = ruoteWorkflow.asyncExecute(workitemFields);
        ruoteRuntime.waitForWorkflow(wfid);
    }

    private static String readRiemannConfigTemplate() {
        URL resource = Resources.getResource("riemann/riemann.config.template");
        try {
            return Resources.toString(resource, Charsets.UTF_8);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

}
