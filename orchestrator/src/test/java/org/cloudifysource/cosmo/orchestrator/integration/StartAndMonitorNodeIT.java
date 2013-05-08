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

package org.cloudifysource.cosmo.orchestrator.integration;

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.cep.Agent;
import org.cloudifysource.cosmo.cep.ResourceMonitorServer;
import org.cloudifysource.cosmo.cep.mock.MockAgent;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.orchestrator.integration.config.BaseOrchestratorIntegrationTestConfig;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.resource.config.CloudResourceProvisionerConfig;
import org.mockito.Mockito;
import org.mockito.invocation.InvocationOnMock;
import org.mockito.stubbing.Answer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.Map;
import java.util.concurrent.ExecutionException;

import static org.mockito.Matchers.any;
import static org.mockito.Mockito.when;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { StartAndMonitorNodeIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class StartAndMonitorNodeIT extends AbstractTestNGSpringContextTests {

    /**
     *
     */
    @Configuration
    @Import({
            CloudResourceProvisionerConfig.class,
            RuoteRuntimeConfig.class
    })
    static class Config extends BaseOrchestratorIntegrationTestConfig {

        @Inject
        private ResourceMonitorServer resourceMonitor;

        @Value("${cosmo.test.resource.id}")
        private String resourceId;

        @Bean
        public CloudDriver cloudDriver() {
            CloudDriver cloudDriver = Mockito.mock(CloudDriver.class);
            when(cloudDriver.startMachine(any(MachineConfiguration.class))).thenAnswer(new Answer() {
                @Override
                public Object answer(InvocationOnMock invocation) throws Throwable {
                    final Agent agent = new Agent();
                    agent.setAgentId(resourceId);
                    resourceMonitor.insertFact(agent);
                    return new MachineDetails(resourceId, "127.0.0.1");
                }
            });
            return cloudDriver;
        }
    }

    @Value("${cosmo.test.resource.id}")
    private String resourceId;

    @Inject
    private MockAgent mockAgent;

    @Inject
    private RuoteRuntime runtime;

    @Test(timeOut = 30000)
    public void testStartAndMonitor() throws ExecutionException, InterruptedException {

        // Create radial workflow
        final String flow =
                "define flow\n" +
                        "  resource resource_id: \"$resource_id\", action: \"start_machine\"\n" +
                        "  state resource_id: \"$resource_id\", reachable: \"true\"\n";
        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, runtime);

        // Execute workflow
        final Map<String, Object> workitem = Maps.newHashMap();
        workitem.put("resource_id", resourceId);
        workflow.execute(workitem);
        mockAgent.validateNoFailures();
    }

}
