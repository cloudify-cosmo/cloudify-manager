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

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.orchestrator.integration.config.MockPortKnockerConfig;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.orchestrator.workflow.config.DefaultRuoteWorkflowConfig;
import org.cloudifysource.cosmo.statecache.config.RealTimeStateCacheConfig;
import org.cloudifysource.cosmo.tasks.config.CeleryWorkerProcessConfig;
import org.cloudifysource.cosmo.tasks.config.EventHandlerConfig;
import org.cloudifysource.cosmo.tasks.config.JythonProxyConfig;
import org.cloudifysource.cosmo.tasks.config.TaskExecutorConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.Map;

/**
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
            MockMessageConsumerConfig.class,
            MockMessageProducerConfig.class,
            RealTimeStateCacheConfig.class,
            DefaultRuoteWorkflowConfig.class,
            RuoteRuntimeConfig.class,
            MockPortKnockerConfig.class,
            TaskExecutorConfig.class ,
            EventHandlerConfig.class ,
            JythonProxyConfig.class ,
            CeleryWorkerProcessConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private RuoteRuntime ruoteRuntime;

    @Inject
    private RuoteWorkflow ruoteWorkflow;

    @Test(groups = "vagrant", enabled = false)
    public void testWithVagrantHostProvisionerAndSimpleWebServerInstaller() {
        final String dslLocation = "org/cloudifysource/cosmo/dsl/integration_phase1/integration-phase1.yaml";
        final Map<String, Object> workitemFields = Maps.newHashMap();
        workitemFields.put("dsl", dslLocation);

        final Object wfid = ruoteWorkflow.asyncExecute(workitemFields);
        ruoteRuntime.waitForWorkflow(wfid);
    }

    @Test(groups = "vagrant")
    public void testWithVagrantHostProvisionerAndRemoteCeleryWorker() {
        final String dslLocation = "org/cloudifysource/cosmo/dsl/integration_phase3/integration-phase3.yaml";
        final Map<String, Object> workitemFields = Maps.newHashMap();
        workitemFields.put("dsl", dslLocation);

        final Object wfid = ruoteWorkflow.asyncExecute(workitemFields);
        ruoteRuntime.waitForWorkflow(wfid);
    }

}
