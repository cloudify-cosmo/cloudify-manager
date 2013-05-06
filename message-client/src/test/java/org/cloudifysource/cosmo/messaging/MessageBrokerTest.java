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
import org.cloudifysource.cosmo.messaging.configuration.MessageClientTestConfiguration;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
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
@ContextConfiguration(classes = { MessageClientTestConfiguration.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class MessageBrokerTest extends AbstractTestNGSpringContextTests {

    @Inject
    MessageBrokerServer broker;

    @Inject
    private MessageConsumer consumer;

    @Inject
    private MessageProducer producer;

    private final String key = "r1";
    private List<Throwable> consumerErrors = Lists.newCopyOnWriteArrayList();


    @Test
    public void testPubSub() throws InterruptedException, IOException, ExecutionException {
        final URI topic = broker.getUri().resolve(key);
        final int numberOfEvents = 10;

        final CountDownLatch latch = new CountDownLatch(numberOfEvents);
        consumer.addListener(topic, new MessageConsumerListener<Integer>() {
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
        });

        for (int i = 0; latch.getCount() > 0; i++) {
            //Reducing this sleep period would result in event loss
            //see https://github.com/Atmosphere/atmosphere/wiki/Understanding-BroadcasterCache
            Thread.sleep(100);
            producer.send(topic, i).get();
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
