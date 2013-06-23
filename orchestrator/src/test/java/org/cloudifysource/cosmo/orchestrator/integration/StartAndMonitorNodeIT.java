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

import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.monitor.Agent;
import org.cloudifysource.cosmo.monitor.ResourceMonitorServer;
import org.cloudifysource.cosmo.monitor.mock.MockAgent;
import org.cloudifysource.cosmo.orchestrator.integration.config.BaseOrchestratorIntegrationTestConfig;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.provisioner.config.CloudResourceProvisionerConfig;
import org.cloudifysource.cosmo.tasks.MockCeleryTaskWorker;
import org.cloudifysource.cosmo.tasks.TaskReceivedListener;
import org.cloudifysource.cosmo.tasks.config.MockCeleryTaskWorkerConfig;
import org.cloudifysource.cosmo.tasks.config.MockTaskExecutorConfig;
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.mockito.Mockito;
import org.mockito.invocation.InvocationOnMock;
import org.mockito.stubbing.Answer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Map;
import java.util.concurrent.ExecutionException;

import static org.mockito.Matchers.any;
import static org.mockito.Mockito.when;

/**
 * Integration test for the following components:
 *  1. Ruote workflow.
 *  2. Real time state cache.
 *  3. Cloud resource provisioner.
 *  4. Drools.
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
            MockTaskExecutorConfig.class,
            MockCeleryTaskWorkerConfig.class,
            RuoteRuntimeConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends BaseOrchestratorIntegrationTestConfig {

        @Inject
        private ResourceMonitorServer resourceMonitor;

        @Value("${cosmo.test.resource.id}")
        private String resourceId;

        @Value("cosmo.resource-provisioner.topic")
        private String resourceProvisionerTopic;

        @Inject
        private MessageConsumer messageConsumer;

        @Inject
        private MessageProducer messageProducer;

        @Bean
        public CloudDriver cloudDriver() throws URISyntaxException {
            final CloudDriver cloudDriver = Mockito.mock(CloudDriver.class);
            when(cloudDriver.startMachine(any(MachineConfiguration.class))).thenAnswer(new Answer() {
                @Override
                public Object answer(InvocationOnMock invocation) throws Throwable {
                    System.out.println("-- cloud driver invoked --");
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

    @Value("${cosmo.resource-provisioner.topic}")
    private String resourceProvisionerTopic;

    @Inject
    private MockAgent mockAgent;

    @Inject
    private RuoteRuntime runtime;

    @Inject
    private MessageProducer messageProducer;

    @Inject
    private MockCeleryTaskWorker worker;

    @Test(timeOut = 30000)
    public void testStartAndMonitor() throws ExecutionException, InterruptedException {

        // Create radial workflow
        final String flow = String.format(
                "define flow\n" +
                        "  execute_task target: \"%s\", exec: \"%s\", payload: {\n" +
                        "    resource_id: \"$resource_id\"\n" +
                        "  }\n" +
                        "  state resource_id: \"$resource_id\", reachable: \"true\"\n",
                resourceProvisionerTopic,
                "start_machine");
        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, runtime);

        worker.addListener(resourceProvisionerTopic, new TaskReceivedListener() {

            @Override
            public void onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {

                ExecuteTaskMessage message = new ExecuteTaskMessage();
                message.setTarget(target);
                message.setPayloadProperty("resource_id", resourceId);
                message.setPayloadProperty("exec", taskName);
                try {
                    messageProducer.send(new URI(target), message);
                } catch (URISyntaxException e) {
                    throw Throwables.propagate(e);
                }

            }
        });


        // Execute workflow
        final Map<String, Object> workitem = Maps.newHashMap();
        workitem.put("resource_id", resourceId);
        workflow.execute(workitem);
        mockAgent.validateNoFailures();
    }

}
