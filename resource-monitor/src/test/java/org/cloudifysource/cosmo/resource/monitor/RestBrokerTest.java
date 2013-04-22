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
package org.cloudifysource.cosmo.resource.monitor;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import org.atmosphere.wasync.Client;
import org.atmosphere.wasync.Function;
import org.atmosphere.wasync.Request;
import org.atmosphere.wasync.RequestBuilder;
import org.atmosphere.wasync.Socket;
import org.cloudifysource.cosmo.broker.RestBrokerServer;
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

import org.atmosphere.wasync.ClientFactory;

/**
 * Tests {@link RestBrokerServer} and {@link org.cloudifysource.cosmo.broker.RestBrokerServlet}.
 * @author itaif
 * @since 0.1
 */
public class RestBrokerTest {

    RestBrokerServer server;

    private URI uri;
    private Client client;
    private final String key = "r1";
    private List<Throwable> consumerErrors = Lists.newCopyOnWriteArrayList();

    @BeforeMethod
    @Parameters({"port" })
    public void startRestServer(@Optional("8080") int port) {
        server = new RestBrokerServer();
        server.start(port);
        client = ClientFactory.getDefault().newClient();
        uri = URI.create("http://localhost:" + port);
    }

    @AfterMethod(alwaysRun = true)
    public void stopRestServer() {
        if (server != null) {
            server.stop();
        }
    }

    @Test
    public void testPubSub() throws InterruptedException, IOException, ExecutionException {
        final URI uri = this.uri.resolve("/" + key);
        final int numberOfEvents = 10;

        final CountDownLatch latch = new CountDownLatch(numberOfEvents);
        final RequestBuilder request =
                client.newRequestBuilder()
                  .method(Request.METHOD.GET)
                  .uri(uri.toString())
                .transport(Request.TRANSPORT.STREAMING);

        consumer(latch, request);

        Socket producerSocket = client.create().open(request.build());

        for (int i = 0; latch.getCount() > 0; i++) {
            //Reducing this sleep period would result in event loss
            //see https://github.com/Atmosphere/atmosphere/wiki/Understanding-BroadcasterCache
            Thread.sleep(100);
            producerSocket.fire(String.valueOf(i)).get();
            checkForConsumerErrors();
        }
    }

    private void checkForConsumerErrors() {
        Throwable consumerError = Iterables.getFirst(consumerErrors, null);
        if (consumerError != null) {
            throw Throwables.propagate(consumerError);
        }
    }

    /**
     * calls latch.countDown() each time a message is received.
     */
    private void consumer(final CountDownLatch latch, RequestBuilder request) throws IOException {
        Socket consumerSocket = client.create();
        consumerSocket.on(new Function<String>() {
            Integer lastI = null;
            @Override
            public void on(String message) {
                if (!message.equals("OPEN")) {
                    int i = Integer.valueOf(message);

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

            }
        }).on(new Function<Throwable>() {

            @Override
            public void on(Throwable t) {
                handleConsumerError(t);
            }
        }).open(request.build());
    }

    private void handleConsumerError(Throwable t) {
        consumerErrors.add(t);
    }
}
