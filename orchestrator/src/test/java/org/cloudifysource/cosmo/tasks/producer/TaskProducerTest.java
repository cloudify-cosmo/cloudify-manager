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

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.tasks.messages.TaskMessage;
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
 * Tests {@link TaskProducer} functionality.
 *
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { TaskProducerTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class TaskProducerTest extends AbstractTestNGSpringContextTests {

    @Inject
    private MessageProducer producer;
    @Inject
    private MessageConsumer consumer;
    @Inject
    private TaskProducer taskProducer;
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
        final CountDownLatch latch = new CountDownLatch(1);
        consumer.addListener(topic, new MessageConsumerListener<TaskMessage>() {
            @Override
            public void onMessage(URI uri, TaskMessage message) {
                final Map<String, Object> data = message.getPayload();
                if (data.containsKey("text") && "hello".equals(data.get("text"))) {
                    latch.countDown();
                }
            }

            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });
        final TaskMessage task = createTask();
        taskProducer.send(topic, task);
        assertThat(latch.await(5, TimeUnit.SECONDS)).isTrue();
    }

    @Test
    public void testMessageSentListener() throws InterruptedException {
        final TaskMessage task = createTask();
        final CountDownLatch latch = new CountDownLatch(1);
        taskProducer.send(topic, task, new TaskProducerListener() {
            @Override
            public void onTaskUpdateReceived(TaskMessage result) {
                if (TaskMessage.TASK_SENT.equals(result.getStatus())) {
                    latch.countDown();
                }
            }
            @Override
            public void onFailure(Throwable t) {
            }
        });
        assertThat(latch.await(5, TimeUnit.SECONDS)).isTrue();
    }

    @Test
    public void testMessageReceivedListener() throws InterruptedException, ExecutionException {
        final TaskMessage task = createTask();
        final CountDownLatch latch1 = new CountDownLatch(1);
        final CountDownLatch latch2 = new CountDownLatch(1);
        taskProducer.send(topic, task, new TaskProducerListener() {
            @Override
            public void onTaskUpdateReceived(TaskMessage result) {
                if (result.getTaskId().equals(task.getTaskId())) {
                    if (TaskMessage.TASK_SENT.equals(result.getStatus())) {
                        latch1.countDown();
                    } else if (TaskMessage.TASK_RECEIVED.equals(result.getStatus())) {
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
        final TaskMessage taskResult = createTask();
        taskResult.setTaskId(task.getTaskId());
        taskResult.setStatus(TaskMessage.TASK_RECEIVED);
        System.out.println("!! sending message: " + taskResult);
        producer.send(topic, taskResult).get();
        assertThat(latch2.await(5, TimeUnit.SECONDS)).isTrue();
    }


    @Test(expectedExceptions = RuntimeException.class, enabled = false)
    public void testSentMessageNotReceivedByBroker() throws ExecutionException, InterruptedException {
        final TaskMessage task = createTask();
        taskProducer.send(topic, task, new TaskProducerListener() {
            @Override
            public void onTaskUpdateReceived(TaskMessage result) {

            }

            @Override
            public void onFailure(Throwable t) {
            }
        });
    }

    private TaskMessage createTask() {
        final Map<String, Object> payload = Maps.newHashMap();
        payload.put("text", "hello");
        final TaskMessage task = new TaskMessage();
        task.setPayload(payload);
        task.setStatus(TaskMessage.TASK_CREATED);
        return task;
    }



}
