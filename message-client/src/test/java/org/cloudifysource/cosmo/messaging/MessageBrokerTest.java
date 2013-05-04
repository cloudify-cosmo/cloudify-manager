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
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.io.IOException;
import java.net.URI;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;

/**
 * Tests {@link MessageBrokerServer}.
 * @author itaif
 * @since 0.1
 */
public class MessageBrokerTest {

    MessageBrokerServer server;

    private URI uri;
    private MessageConsumer consumer;
    private MessageProducer producer;
    private final String key = "r1";
    private List<Throwable> consumerErrors = Lists.newCopyOnWriteArrayList();

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
        final int numberOfEvents = 10;

        final CountDownLatch latch = new CountDownLatch(numberOfEvents);
        consumer.addListener(uri, new MessageConsumerListener<Integer>() {
            Integer lastI = null;
            @Override
            public void onMessage(URI uri, Integer i) {

                if (lastI != null && i > lastI + 1) {
                    for (lastI++; lastI < i; lastI++) {
                        System.err.println("lost :" + lastI);
                    }
                }
                if (lastI != null && i < lastI) {
                    System.err.println("out-of-order :" + i);
                } else {
                    System.out.println("received: " + i);
                }
                if (lastI == null || i > lastI) {
                    lastI = i;
                }
                latch.countDown();
            }

            @Override
            public void onFailure(Throwable t) {
                consumerErrors.add(t);
            }

            @Override
            public Class<? extends Integer> getMessageClass() {
                return Integer.class;
            }
        });

        for (int i = 0; latch.getCount() > 0; i++) {
            //Reducing this sleep period would result in event loss
            //see https://github.com/Atmosphere/atmosphere/wiki/Understanding-BroadcasterCache
            Thread.sleep(100);
            producer.send(uri, i).get();
            checkForConsumerErrors();
        }
    }

    private void checkForConsumerErrors() {
        Throwable consumerError = Iterables.getFirst(consumerErrors, null);
        if (consumerError != null) {
            throw Throwables.propagate(consumerError);
        }
    }
}
