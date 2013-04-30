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

package org.cloudifysource.cosmo.statecache;

import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;

/**
 * Tests integration of {@link StateCache} with messaging consumer.
 * @author itaif
 * @since 0.1
 */
public class StateCacheMessagingIT {

    // message broker that isolates server
    private MessageBrokerServer broker;
    private URI inputUri;
    private MessageProducer producer;
    private RealTimeStateCache cache;

    @Test(timeOut = 5000)
    public void testNodeOk() {
        StateChangedMessage message = new StateChangedMessage();
        message.setResourceId("node_1");
        message.setReachable(true);
        producer.send(inputUri, message);
        //TODO: complete test
        //ListenableFuture future = cache.waitForState();
        //future.get();
        //check node state is reachable
    }


    @BeforeMethod
    @Parameters({"port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        inputUri = URI.create("http://localhost:" + port + "/input/");
        producer = new MessageProducer();
        RealTimeStateCacheConfiguration config =
                new RealTimeStateCacheConfiguration();
        config.setMessageTopic(inputUri);
        cache = new RealTimeStateCache(config);
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        stopMessageBroker();
    }

    private void startMessagingBroker(int port) {
        broker = new MessageBrokerServer();
        broker.start(port);
    }

    private void stopMessageBroker() {
        if (broker != null) {
            broker.stop();
        }
    }
}
