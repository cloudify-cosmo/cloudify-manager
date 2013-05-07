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
import org.cloudifysource.cosmo.cep.ResourceMonitorServer;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.integration.config.BaseOrchestratorIntegrationTestConfig;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.resource.config.CloudResourceProvisionerConfig;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
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
import java.net.URI;
import java.util.Map;
import java.util.concurrent.ExecutionException;

import static org.mockito.Matchers.any;
import static org.mockito.Mockito.when;

/**
 * Tests integration of {@link org.cloudifysource.cosmo.statecache.StateCache} with messaging consumer.
 * @author itaif
 * @since 0.1
 */
@ContextConfiguration(classes = { StateCacheWorkflowMessagingIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class StateCacheWorkflowMessagingIT extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @Import({
            CloudResourceProvisionerConfig.class,
            RuoteRuntimeConfig.class
    })
    static class Config extends BaseOrchestratorIntegrationTestConfig {

        @Inject
        private ResourceMonitorServer resourceMonitor;

        @Inject
        private MessageProducer producer;

        @Value("${state-cache.topic}")
        private URI stateCacheTopic;

        @Value("${test.resource.id}")
        private String resourceId;

        @Bean
        public CloudDriver cloudDriver() {
            CloudDriver cloudDriver = Mockito.mock(CloudDriver.class);
            // Configure mock cloud driver
            when(cloudDriver.startMachine(any(MachineConfiguration.class))).thenAnswer(new Answer() {
                @Override
                public Object answer(InvocationOnMock invocation) throws Throwable {
                    // Update state cache
                    final StateChangedMessage message = newStateChangedMessage(resourceId);
                    producer.send(stateCacheTopic, message).get();
                    return new MachineDetails(resourceId, "127.0.0.1");
                }
            });
            return cloudDriver;
        }

        private StateChangedMessage newStateChangedMessage(String resourceId) {
            final StateChangedMessage message = new StateChangedMessage();
            message.setResourceId(resourceId);
            message.setState(newState());
            return message;
        }

        private Map<String, Object> newState() {
            Map<String, Object> state = Maps.newLinkedHashMap();
            state.put("reachable", "true");
            return state;
        }

    }

    @Value("${test.resource.id}")
    private String resourceId;

    @Inject
    private RuoteRuntime runtime;

    @Test(timeOut = 30000)
    public void testMessaging() throws ExecutionException, InterruptedException {

        // Create radial workflow
        final String flow =
                "define flow\n" +
                "  resource resource_id: \"$resource_id\", action: \"start_machine\"\n" +
                "  state resource_id: \"$resource_id\", reachable: \"true\"\n";
        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, runtime);

        // Execute workflow
        final Map<String, Object> workitem = Maps.newHashMap();
        workitem.put("resource_id", resourceId);
        final Object workflowId = workflow.asyncExecute(workitem);

        // Wait for workflow to end
        runtime.waitForWorkflow(workflowId);
    }


}
