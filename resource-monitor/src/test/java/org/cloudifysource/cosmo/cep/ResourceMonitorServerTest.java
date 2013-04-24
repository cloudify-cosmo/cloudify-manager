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
package org.cloudifysource.cosmo.cep;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.cep.mock.AppInfo;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.drools.io.Resource;
import org.drools.io.ResourceFactory;
import org.drools.time.SessionPseudoClock;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Date;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests {@link ResourceMonitorServer}.
 *
 * @author itaif
 * @since 0.1
 */
public class ResourceMonitorServerTest {

    private static final String RULE_FILE = "/org/cloudifysource/cosmo/cep/AgentFailureDetector.drl";
    public static final String AGENT_ID = "agent_1";

    // component being tested
    private ResourceMonitorServer server;

    // message broker that isolates server
    private MessageBrokerServer broker;

    // used to receive consumedMessages from server
    private MessageConsumer consumer;

    // used to push consumedMessages into server
    private MessageProducer producer;
    private URI inputUri;
    private URI outputUri;
    private MessageConsumerListener<StateChangedMessage> listener;
    private List<StateChangedMessage> consumedMessages;
    private List<Throwable> failures;

    @BeforeMethod
    @Parameters({"port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        inputUri = URI.create("http://localhost:" + port + "/input/");
        outputUri = URI.create("http://localhost:" + port + "/output/");
        producer = new MessageProducer();
        consumer = new MessageConsumer();
        consumedMessages = Lists.newCopyOnWriteArrayList();
        failures = Lists.newCopyOnWriteArrayList();
        listener = new MessageConsumerListener<StateChangedMessage>() {
            @Override
            public void onMessage(URI uri, StateChangedMessage message) {
                assertThat(uri).isEqualTo(outputUri);
                consumedMessages.add(message);
            }

            @Override
            public void onFailure(Throwable t) {
                failures.add(t);
            }

            @Override
            public Class<? extends StateChangedMessage> getMessageClass() {
                return StateChangedMessage.class;
            }
        };
        consumer.addListener(outputUri, listener);
        startMonitoringServer(port);
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        consumer.removeListener(listener);
        stopMonitoringServer();
        stopMessageBroker();
    }

    @Test(timeOut = 5000)
    public void testMissingEvent() throws InterruptedException {
        Agent agent = new Agent();
        agent.setAgentId("agent_1");
        server.insertFact(agent);

        for (int i = 0 ; i < 10 ; i ++) {
            getClock().advanceTime(10, TimeUnit.SECONDS);
            checkFailures();
            Thread.sleep(10);
        }

        assertThat(consumedMessages.size()).isGreaterThan(0);
        final StateChangedMessage stateChange =
                consumedMessages.get(0);
        assertThat(stateChange.getResourceId()).isEqualTo(AGENT_ID);
    }

    private void checkFailures() {
        final Throwable t = Iterables.getFirst(failures, null);
        if (t != null) {
            throw Throwables.propagate(t);
        }
    }

    private SessionPseudoClock getClock() {
        return ((SessionPseudoClock) server.getClock());
    }

    private void fireAppInfo() {
        AppInfo appInfo = new AppInfo();
        appInfo.setTimestamp(now());
        producer.send(inputUri, appInfo);
    }

    private void startMonitoringServer(int port) {
        ResourceMonitorServerConfiguration config =
                new ResourceMonitorServerConfiguration();
        config.setPseudoClock(true);
        final Resource resource = ResourceFactory.newClassPathResource(RULE_FILE, this.getClass());
        config.setDroolsResource(resource);
        config.setInputUri(inputUri);
        config.setOutputUri(outputUri);
        server = new ResourceMonitorServer(config);
        server.start();
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

    private void stopMonitoringServer() {
        if (server != null) {
            server.stop();
        }
    }

    private Date now() {
        return new Date(getClock().getCurrentTime());
    }
}
