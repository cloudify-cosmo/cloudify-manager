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
                .transport(Request.TRANSPORT.LONG_POLLING);

        consumer(latch, request);
        producer(latch, request);
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
                    if (lastI == null || i == lastI + 1) {
                        System.out.println("received: " + i);
                        lastI = i;
                    } else if (lastI != null && i != lastI + 1) {
                        System.err.println("expected: " + (lastI + 1) + " actual :" + i);
                    }
                    latch.countDown();
                }

            }
        }).on(new Function<Throwable>() {

            @Override
            public void on(Throwable t) {
                throw Throwables.propagate(t);
            }
        }).open(request.build());
    }

    /**
     * Fires new events until latch count is zero.
     */
    private void producer(CountDownLatch latch, RequestBuilder request)
        throws IOException, InterruptedException {
        Socket producerSocket = client.create().open(request.build());
        int i = 0;
        while (latch.getCount() > 0) {
            Thread.sleep(10);
            producerSocket.fire(String.valueOf(i));
            i++;
        }
    }
}
