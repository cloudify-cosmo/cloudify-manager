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
package org.cloudifysource.cosmo.messaging;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Queues;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.config.MessageClientTestConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.messages.MockMessage;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URI;
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests {@link MessageConsumer} and {@link MessageProducer}.
 * @author itaif
 * @since 0.1
 */
@ContextConfiguration(classes = { MessageClientTestConfig.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class ConsumerProducerTest extends AbstractTestNGSpringContextTests {

    @Inject
    MessageBrokerServer server;

    @Inject
    private MessageConsumer consumer;

    @Inject
    private MessageProducer producer;

    private List<Throwable> failures = Lists.newCopyOnWriteArrayList();

    @Test
    public void testPubSub() throws InterruptedException, IOException, ExecutionException {
        final URI topic = server.getUri().resolve("x");
        testPubSub(topic);
    }

    @Test
    public void testSubTopic() throws InterruptedException, IOException, ExecutionException {
        final URI topic = server.getUri().resolve("xxx/xxx/");
        testPubSub(topic);
    }

    //TODO: Support underscores in URIs
    @Test(expectedExceptions = {IllegalArgumentException.class })
    public void testUnderscoreSubTopic() throws InterruptedException, IOException, ExecutionException {
        final URI topic = server.getUri().resolve("x_x/");
        testPubSub(topic);
    }

    private void testPubSub(final URI topic) throws ExecutionException, InterruptedException {
        final BlockingQueue<MockMessage> messages = Queues.newArrayBlockingQueue(1);
        consumer.addListener(topic, new MessageConsumerListener<MockMessage>() {

            @Override
            public void onMessage(URI messageUri, MockMessage message) {
                assertThat(messageUri).isEqualTo(topic);
                messages.add(message);
            }

            @Override
            public void onFailure(Throwable t) {
                failures.add(t);
            }
        });

        MockMessage message = new MockMessage();
        message.setValue(1);

        producer.send(topic, message).get();

        MockMessage message2 = null;
        while (message2 == null) {
            message2 = messages.poll(1, TimeUnit.SECONDS);
            checkFailures();
        }
        assertThat(message).isEqualTo(message2);
    }

    private void checkFailures() {
        final Throwable t = Iterables.getFirst(failures, null);
        if (t != null) {
            throw Throwables.propagate(t);
        }
    }
}
