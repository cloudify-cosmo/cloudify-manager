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
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.messages.MockMessage;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

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
public class ConsumerProducerTest {

    MessageBrokerServer server;

    private URI uri;
    private MessageConsumer consumer;
    private MessageProducer producer;
    private final String key = "r1";
    private List<Throwable> failures = Lists.newCopyOnWriteArrayList();

    @BeforeMethod
    @Parameters({"port" })
    public void startRestServer(@Optional("8080") int port) {
        server = new MessageBrokerServer();
        server.start(port);
        consumer = new MessageConsumer();
        producer = new MessageProducer();
        uri = URI.create("http://localhost:" + port);
    }

    @AfterMethod(alwaysRun = true)
    public void stopRestServer() {
        consumer.removeAllListeners();
        if (server != null) {
            server.stop();
        }
    }

    @Test
    public void testPubSub() throws InterruptedException, IOException, ExecutionException {
        final URI uri = this.uri.resolve("/" + key);

        final BlockingQueue<MockMessage> messages = Queues.newArrayBlockingQueue(1);
        consumer.addListener(uri, new MessageConsumerListener<MockMessage>() {
            Integer lastI = null;
            @Override
            public void onMessage(URI messageUri, MockMessage message) {
                assertThat(messageUri).isEqualTo(uri);
                messages.add(message);
            }

            @Override
            public void onFailure(Throwable t) {
                failures.add(t);
            }

            @Override
            public Class<? extends MockMessage> getMessageClass() {
                return MockMessage.class;
            }
        });

        MockMessage message = new MockMessage();
        message.setValue(1);

        producer.send(uri, message);

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
