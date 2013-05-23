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

import com.google.common.base.Objects;
import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.statecache.config.RealTimeStateCacheConfig;
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.cloudifysource.cosmo.tasks.messages.TaskStatusMessage;
import org.fest.assertions.api.Assertions;
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
import java.net.URISyntaxException;
import java.util.concurrent.BrokenBarrierException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.fest.assertions.api.Assertions.assertThat;

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
    @Import({
            MockMessageConsumerConfig.class,
            MockMessageProducerConfig.class,
            RealTimeStateCacheConfig.class,
            RuoteRuntimeConfig.class })
    static class Config extends TestConfig {
    }

    @Inject
    private MessageConsumer messageConsumer;

    @Inject
    private MessageProducer messageProducer;

    @Value("${cosmo.resource-provisioner.topic}")
    private String target;

    @Inject
    private RuoteRuntime runtime;


    @Test(timeOut = 30000)
    public void testTaskExecution() throws URISyntaxException, InterruptedException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CountDownLatch latch = new CountDownLatch(1);

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", payload: {\n" +
                "    exec: \"%s\",\n" +
                "    resource_id: \"%s\"\n" +
                "  }\n", target, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        messageConsumer.addListener(new URI(target), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                if (message instanceof ExecuteTaskMessage) {
                    final ExecuteTaskMessage executeTaskMessage = (ExecuteTaskMessage) message;
                    boolean valid = Objects.equal(executeTaskMessage.getSender(), "execute_task_participant");
                    valid &= Objects.equal(executeTaskMessage.getTarget(), target);
                    valid &= Objects.equal(executeTaskMessage.getPayloadProperty("exec").get(), execute);
                    valid &= Objects.equal(executeTaskMessage.getPayloadProperty("resource_id").get(), resourceId);
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

    @Test(timeOut = 30000)
    public void testTaskExecutionContinueOn() throws URISyntaxException, InterruptedException, BrokenBarrierException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CyclicBarrier barrier = new CyclicBarrier(2);
        final AtomicBoolean started = new AtomicBoolean(false);
        final StringBuilder taskId = new StringBuilder();

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", continue_on: \"%s\", payload: {\n" +
                "    exec: \"%s\",\n" +
                "    resource_id: \"%s\"\n" +
                "  }\n", target, TaskStatusMessage.STARTED, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        messageConsumer.addListener(new URI(target), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                try {
                    if (message instanceof ExecuteTaskMessage) {
                        taskId.append(((ExecuteTaskMessage) message).getTaskId());
                        barrier.await();
                    } else if (message instanceof TaskStatusMessage) {
                        final TaskStatusMessage statusMessage = (TaskStatusMessage) message;
                        barrier.await();
                        if (Objects.equal(statusMessage.getStatus(), TaskStatusMessage.STARTED)) {
                            started.set(true);
                        }
                    }
                } catch (Exception e) {
                    Throwables.propagate(e);
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });

        // Start workflow
        final Object id = workflow.asyncExecute();

        // Wait until new task message is sent
        barrier.await();

        // Send task message status received
        final TaskStatusMessage status = new TaskStatusMessage();
        status.setTaskId(taskId.toString());
        status.setStatus(TaskStatusMessage.RECEIVED);
        messageProducer.send(new URI(target), status);

        // Wait until status is received
        barrier.await();

        // Send task message status started
        status.setStatus(TaskStatusMessage.STARTED);
        messageProducer.send(new URI(target), status);

        // Wait until status is received
        barrier.await();

        // Wait for workflow to end
        runtime.waitForWorkflow(id);

        // Assert
        assertThat(started.get()).isTrue();
    }

    @Test(timeOut = 30000)
    public void testTaskExecutionFailure() throws URISyntaxException, InterruptedException, BrokenBarrierException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CyclicBarrier barrier = new CyclicBarrier(2);
        final StringBuilder taskId = new StringBuilder();

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", payload: {\n" +
                "    exec: \"%s\",\n" +
                "    resource_id: \"%s\"\n" +
                "  }\n", target, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        messageConsumer.addListener(new URI(target), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                try {
                    if (message instanceof ExecuteTaskMessage) {
                        taskId.append(((ExecuteTaskMessage) message).getTaskId());
                        barrier.await();
                    }
                } catch (Exception e) {
                    throw Throwables.propagate(e);
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });

        // Start workflow
        final Object id = workflow.asyncExecute();

        // Wait until new task message is sent
        barrier.await();

        // Send task message failed status
        final TaskStatusMessage status = new TaskStatusMessage();
        status.setTaskId(taskId.toString());
        status.setStatus(TaskStatusMessage.FAILED);
        messageProducer.send(URI.create(target), status);

        // Wait for workflow to end - should not throw exception because
        // execute_task_participant continues on "sent" status.
        runtime.waitForWorkflow(id);
    }

    @Test(timeOut = 30000)
    public void testTaskExecutionFailureWithContinueOn()
        throws URISyntaxException, InterruptedException, BrokenBarrierException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CyclicBarrier barrier = new CyclicBarrier(2);
        final StringBuilder taskId = new StringBuilder();

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", continue_on: \"%s\",payload: {\n" +
                "    exec: \"%s\",\n" +
                "    resource_id: \"%s\"\n" +
                "  }\n", target, TaskStatusMessage.STARTED, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        messageConsumer.addListener(new URI(target), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                try {
                    if (message instanceof ExecuteTaskMessage) {
                        taskId.append(((ExecuteTaskMessage) message).getTaskId());
                        barrier.await();
                    }
                } catch (Exception e) {
                    throw Throwables.propagate(e);
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });

        // Start workflow
        final Object id = workflow.asyncExecute();

        // Wait until new task message is sent
        barrier.await();

        // Send task message failed status
        final TaskStatusMessage status = new TaskStatusMessage();
        status.setTaskId(taskId.toString());
        status.setStatus(TaskStatusMessage.FAILED);
        messageProducer.send(URI.create(target), status);

        // Wait for workflow to end
        try {
            runtime.waitForWorkflow(id);
            Assertions.fail("Exception expected!");
        } catch (Exception e) {
        }
    }

    @Test(timeOut = 30000)
    public void testTaskExecutionFailureWithContinueOnSent()
        throws URISyntaxException, InterruptedException, BrokenBarrierException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CyclicBarrier barrier = new CyclicBarrier(2);
        final StringBuilder taskId = new StringBuilder();

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", continue_on: \"%s\",payload: {\n" +
                "    exec: \"%s\",\n" +
                "    resource_id: \"%s\"\n" +
                "  }\n", target, TaskStatusMessage.SENT, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        messageConsumer.addListener(new URI(target), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                try {
                    if (message instanceof ExecuteTaskMessage) {
                        taskId.append(((ExecuteTaskMessage) message).getTaskId());
                        barrier.await();
                    }
                } catch (Exception e) {
                    throw Throwables.propagate(e);
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });

        // Start workflow
        final Object id = workflow.asyncExecute();

        // Wait until new task message is sent
        barrier.await();

        // Send task message failed status
        final TaskStatusMessage status = new TaskStatusMessage();
        status.setTaskId(taskId.toString());
        status.setStatus(TaskStatusMessage.FAILED);
        messageProducer.send(URI.create(target), status);

        // Wait for workflow to end - should not throw exception because
        // execute_task_participant continues on "sent" status.
        runtime.waitForWorkflow(id);
    }

}
