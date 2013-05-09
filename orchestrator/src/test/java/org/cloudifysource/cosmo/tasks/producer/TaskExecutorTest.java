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
package org.cloudifysource.cosmo.tasks.producer;

import com.google.common.base.Objects;
import com.google.common.base.Optional;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.mock.MockMessageProducer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.cloudifysource.cosmo.tasks.messages.TaskStatusMessage;
import org.cloudifysource.cosmo.tasks.producer.config.TaskProducerConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.URI;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests {@link TaskExecutor} functionality.
 *
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { TaskExecutorTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class TaskExecutorTest extends AbstractTestNGSpringContextTests {

    @Inject
    private MessageProducer producer;
    @Inject
    private MockMessageProducer mockMessageProducer;
    @Inject
    private MessageConsumer consumer;
    @Inject
    private TaskExecutor taskExecutor;
    @Value("${cosmo.resource-provisioner.topic}")
    private URI topic;

    /**
     *
     */
    @Configuration
    @Import({
            MockMessageConsumerConfig.class,
            MockMessageProducerConfig.class,
            TaskProducerConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Test
    public void testSend() throws InterruptedException {
        final String key = "text";
        final String value = "hello";
        final CountDownLatch latch = new CountDownLatch(1);
        consumer.addListener(topic, new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                final ExecuteTaskMessage executeTaskMessage = (ExecuteTaskMessage) message;
                final Optional<Object> text = executeTaskMessage.get("text");
                if (text.isPresent() && Objects.equal(text.get(), value)) {
                    latch.countDown();
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });
        final ExecuteTaskMessage task = createTask();
        task.put(key, value);
        taskExecutor.send(topic, task);
        assertThat(latch.await(5, TimeUnit.SECONDS)).isTrue();
    }

    @Test
    public void testMessageSentListener() throws InterruptedException {
        final ExecuteTaskMessage task = createTask();
        final CountDownLatch latch = new CountDownLatch(1);
        taskExecutor.send(topic, task, new TaskExecutorListener() {
            @Override
            public void onTaskStatusReceived(TaskStatusMessage message) {
                if (Objects.equal(message.getStatus(), TaskStatusMessage.SENT)) {
                    latch.countDown();
                }
            }
            @Override
            public void onFailure(Throwable t) {
            }
        });
        assertThat(latch.await(5, TimeUnit.SECONDS)).isTrue();
    }

    private ExecuteTaskMessage createTask() {
        return taskExecutor.createTask("server", "client");
    }

    @Test
    public void testMessageReceivedListener() throws InterruptedException, ExecutionException {
        final ExecuteTaskMessage task = createTask();
        final CountDownLatch latch1 = new CountDownLatch(1);
        final CountDownLatch latch2 = new CountDownLatch(1);
        taskExecutor.send(topic, task, new TaskExecutorListener() {
            @Override
            public void onTaskStatusReceived(TaskStatusMessage message) {
                if (Objects.equal(message.getTaskId(), task.getTaskId())) {
                    final String status = message.getStatus();
                    if (Objects.equal(status, TaskStatusMessage.SENT)) {
                        latch1.countDown();
                    } else if (Objects.equal(status, TaskStatusMessage.RECEIVED)) {
                        latch2.countDown();
                    }
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });
        assertThat(latch1.await(5, TimeUnit.SECONDS)).isTrue();

        final TaskStatusMessage taskStatusMessage = new TaskStatusMessage();
        taskStatusMessage.setTaskId(task.getTaskId());
        taskStatusMessage.setStatus(TaskStatusMessage.RECEIVED);
        taskStatusMessage.setTarget(task.getTarget());
        taskStatusMessage.setSender(task.getSender());
        producer.send(topic, taskStatusMessage).get();

        assertThat(latch2.await(5, TimeUnit.SECONDS)).isTrue();
    }

    @Test(timeOut = 5000)
    public void testSentMessageNotReceivedByBroker() throws ExecutionException, InterruptedException {
        mockMessageProducer.setReturnedStatusCode(500);
        final ExecuteTaskMessage task = createTask();
        final CountDownLatch latch = new CountDownLatch(1);
        taskExecutor.send(topic, task, new TaskExecutorListener() {
            @Override
            public void onTaskStatusReceived(TaskStatusMessage message) {
            }
            @Override
            public void onFailure(Throwable t) {
                latch.countDown();
            }
        });
        latch.await();
    }

}
