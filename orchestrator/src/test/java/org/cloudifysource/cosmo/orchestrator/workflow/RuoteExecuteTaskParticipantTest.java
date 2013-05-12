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
package org.cloudifysource.cosmo.orchestrator.workflow;

import com.beust.jcommander.internal.Maps;
import com.google.common.base.Objects;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.tasks.executor.TaskExecutor;
import org.cloudifysource.cosmo.tasks.executor.config.TaskExecutorConfig;
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

/**
 * Tests ruote "execute task" participant.
 *
 * @author Idan Moyal
 * @since 0.1
 */

@ContextConfiguration(classes = { RuoteExecuteTaskParticipantTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RuoteExecuteTaskParticipantTest extends AbstractTestNGSpringContextTests {

    /**
     * Test configuration.
     */
    @Configuration
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    @Import({ MockMessageConsumerConfig.class, MockMessageProducerConfig.class, TaskExecutorConfig.class })
    static class Config extends TestConfig {
    }

    @Inject
    private MessageConsumer messageConsumer;
    @Inject
    private MessageProducer messageProducer;
    @Value("${cosmo.resource-provisioner.topic}")
    private String target;

    // TODO: add @Inject annotation
    private RuoteRuntime runtime;

    @BeforeMethod
    public void beforeMethod() {
        final Map<String, Object> properties = Maps.newHashMap();
        properties.put("message_producer", messageProducer);
        properties.put("message_consumer", messageConsumer);
        runtime = RuoteRuntime.createRuntime(properties);
    }

    @Test(timeOut = 30000)
    public void testTaskExecution() throws URISyntaxException, InterruptedException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CountDownLatch latch = new CountDownLatch(1);

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", payload: {\n" +
                "    exec: \"%s\",\n" +
                "    resource_id: \"%s\", timeout: 5s\n" +
                "  }\n", target, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        messageConsumer.addListener(new URI(target), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                if (message instanceof ExecuteTaskMessage) {
                    final ExecuteTaskMessage executeTaskMessage = (ExecuteTaskMessage) message;
                    boolean valid = Objects.equal(executeTaskMessage.getSender(), "execute_task_participant");
                    valid &= Objects.equal(executeTaskMessage.getTarget(), target);
                    valid &= Objects.equal(executeTaskMessage.get("exec").get(), execute);
                    valid &= Objects.equal(executeTaskMessage.get("resource_id").get(), resourceId);
                    if (valid) {
                        latch.countDown();
                    }
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });

        final Object id = workflow.asyncExecute();
        latch.await();
        runtime.waitForWorkflow(id);
    }


}
