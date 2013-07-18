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
 ******************************************************************************/

package org.cloudifysource.cosmo.orchestrator.integration.riemann;

import com.aphyr.riemann.Proto;
import com.google.common.base.Throwables;
import com.google.common.collect.Queues;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.robobninjas.riemann.json.RiemannEvent;
import org.robobninjas.riemann.json.RiemannEventObjectMapper;
import org.robobninjas.riemann.spring.RiemannTestConfiguration;
import org.robotninjas.riemann.client.RiemannTcpClient;
import org.robotninjas.riemann.client.RiemannTcpConnection;
import org.robotninjas.riemann.pubsub.QueryResultListener;
import org.robotninjas.riemann.pubsub.RiemannPubSubClient;
import org.robotninjas.riemann.pubsub.RiemannPubSubConnection;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URISyntaxException;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Integration test for riemann custom streams dedicated for vagrant status events.
 *
 * 1. Publish a generic vagrant status event.
 * 2. Check reimann index is enriched with cosmo events caused by the stream processing.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@ContextConfiguration(classes = { RiemannVagrantStreamProcessingIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RiemannVagrantStreamProcessingIT extends AbstractTestNGSpringContextTests {

    private static final String VAGRANT_SERVICE = "vagrant machine status";
    private static final String HOST_ID = "host_id";

    private BlockingQueue<String> ipEvents = Queues.newArrayBlockingQueue(1);
    private BlockingQueue<String> reachableEvents = Queues.newArrayBlockingQueue(1);

    protected Logger logger = LoggerFactory.getLogger(RiemannVagrantStreamProcessingIT.class);


    /**
     */
    @Configuration
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    @Import({ RiemannTestConfiguration.class })
    static class Config extends TestConfig {
    }

    @Inject
    private RiemannTcpClient tcpClient;

    @Inject
    private RiemannPubSubClient pubSubClient;

    private RiemannTcpConnection tcpConnection;
    private RiemannPubSubConnection pubSubConnection;

    @Inject
    RiemannEventObjectMapper objectMapper;

    @BeforeMethod
    public void establishConnection() throws InterruptedException {

        // adding sleep to let the riemann process start properly
        // see https://github.com/mgodave/riemann-client/issues/13

        Thread.sleep(5 * 1000);

        tcpConnection = makeConnection();
        pubSubConnection = continuousQuery();
    }

    @AfterMethod
    public void closeConnection() throws IOException, InterruptedException {
        if (tcpConnection != null) {
            tcpConnection.close();
        }
        if (pubSubConnection != null) {
            pubSubConnection.close();
        }
    }

    @Test(timeOut = 60 * 1000)
    public void testMachineRunning() throws InterruptedException, IOException {

        Proto.Event running = Proto.Event.newBuilder()
                .setHost("10.0.0.5")
                .setService(VAGRANT_SERVICE)
                .setState("running")
                .setTtl(10)
                .addTags("name=" + HOST_ID)
                .build();

        // send the raw vagrant event
        logger.debug("Sending event to riemann : " + running);
        tcpConnection.send(running);

        logger.debug("Waiting for processes riemann events...");
        RiemannEvent ipEvent = objectMapper.readEvent(ipEvents.take());
        RiemannEvent reachableEvent = objectMapper.readEvent(reachableEvents.take());

        assertThat(ipEvent.getState()).isEqualTo("10.0.0.5");
        assertThat(ipEvent.getHost()).isEqualTo(HOST_ID);
        assertThat(ipEvent.getTtl()).isEqualTo(10);

        assertThat(reachableEvent.getState()).isEqualTo("true");
        assertThat(reachableEvent.getHost()).isEqualTo(HOST_ID);
        assertThat(reachableEvent.getTtl()).isEqualTo(10);


    }

    @Test(timeOut = 60 * 1000)
    public void testBadTag() throws InterruptedException, IOException {

        Proto.Event running = Proto.Event.newBuilder()
                .setHost("10.0.0.5")
                .setService(VAGRANT_SERVICE)
                .setState("running")
                .addTags("badTag=" + HOST_ID)
                .build();

        // send the raw vagrant event
        tcpConnection.send(running);

        String ipEvent = ipEvents.poll(3, TimeUnit.SECONDS);
        String reachableEvent = reachableEvents.poll(3, TimeUnit.SECONDS);

        assertThat(ipEvent).isNull();
        assertThat(reachableEvent).isNull();

    }

    @Test(timeOut = 60 * 1000)
    public void testNoTag() throws InterruptedException, IOException {

        Proto.Event running = Proto.Event.newBuilder()
                .setHost("10.0.0.5")
                .setService(VAGRANT_SERVICE)
                .setState("running")
                .build();

        // send the raw vagrant event
        tcpConnection.send(running);

        String ipEvent = ipEvents.poll(3, TimeUnit.SECONDS);
        String reachableEvent = reachableEvents.poll(3, TimeUnit.SECONDS);

        assertThat(ipEvent).isNull();
        assertThat(reachableEvent).isNull();

    }

    @Test(timeOut = 60 * 1000)
    public void testWrongService() throws InterruptedException, IOException {

        Proto.Event running = Proto.Event.newBuilder()
                .setHost("10.0.0.5")
                .setService("wrong service")
                .setState("running")
                .addTags("badTag=" + HOST_ID)
                .build();

        // send the raw vagrant event
        tcpConnection.send(running);

        String ipEvent = ipEvents.poll(3, TimeUnit.SECONDS);
        String reachableEvent = reachableEvents.poll(3, TimeUnit.SECONDS);

        assertThat(ipEvent).isNull();
        assertThat(reachableEvent).isNull();

    }

    private RiemannTcpConnection makeConnection() {
        try {
            return tcpClient.makeConnection();
        } catch (InterruptedException e) {
            throw Throwables.propagate(e);
        }
    }

    private String queryString() {
        return "tagged \"cosmo\"";
    }

    private RiemannPubSubConnection continuousQuery() {

        // clear queues before making the new connection.
        // to isolate tests.
        ipEvents.clear();
        reachableEvents.clear();
        try {
            return this.pubSubClient.makeConnection(queryString(), true, new QueryResultListener() {

                @Override
                public void handleResult(String result) {
                    logger.debug("Got Event : " + result);
                    if (result.contains("reachable")) {
                        reachableEvents.add(result);
                    } else {
                        ipEvents.add(result);
                    }
                }
            });
        } catch (InterruptedException e) {
            throw Throwables.propagate(e);
        } catch (URISyntaxException e) {
            throw Throwables.propagate(e);
        }
    }
}
