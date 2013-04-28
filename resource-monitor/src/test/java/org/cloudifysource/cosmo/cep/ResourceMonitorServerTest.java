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
import com.google.common.collect.Queues;
import junit.framework.Assert;
import org.cloudifysource.cosmo.agent.messages.ProbeAgentMessage;
import org.cloudifysource.cosmo.cep.messages.AgentStatusMessage;
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
import java.util.concurrent.BlockingQueue;

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

    // receives messages from server
    private MessageConsumer consumer;

    // pushes messages to server
    private MessageProducer producer;

    private URI inputTopic;
    private URI outputTopic;
    private MessageConsumerListener<Object> listener;
    private BlockingQueue<StateChangedMessage> stateChangedMessages;
    private List<Throwable> failures;
    private boolean mockAgentFailed;

    @Test(groups = "integration")
    public void testAgentUnreachable() throws InterruptedException {
        mockAgentFailed = true;
        boolean reachable = monitorAgentState();
        assertThat(reachable).isFalse();
    }

    @Test(groups = "integration")
    public void testAgentReachable() throws InterruptedException {
        mockAgentFailed = false;
        boolean reachable = monitorAgentState();
        assertThat(reachable).isTrue();
    }

    @BeforeMethod
    @Parameters({"port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        inputTopic = URI.create("http://localhost:" + port + "/input/");
        outputTopic = URI.create("http://localhost:" + port + "/output/");
        producer = new MessageProducer();
        consumer = new MessageConsumer();
        stateChangedMessages = Queues.newArrayBlockingQueue(100);
        failures = Lists.newCopyOnWriteArrayList();
        listener = new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                assertThat(uri).isEqualTo(outputTopic);
                if (message instanceof StateChangedMessage) {
                    stateChangedMessages.add((StateChangedMessage) message);
                } else if (message instanceof ProbeAgentMessage) {
                    mockAgent((ProbeAgentMessage) message);
                } else {
                    Assert.fail("Unexpected message: " + message);
                }
            }

            @Override
            public void onFailure(Throwable t) {
                failures.add(t);
            }

            @Override
            public Class<? extends Object> getMessageClass() {
                return Object.class;
            }
        };
        consumer.addListener(outputTopic, listener);
        startMonitoringServer(port);
    }

    private void mockAgent(ProbeAgentMessage message) {
        if (!mockAgentFailed) {
            final AgentStatusMessage statusMessage = new AgentStatusMessage();
            statusMessage.setAgentId(AGENT_ID);
            producer.send(inputTopic, statusMessage);
        }
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        consumer.removeListener(listener);
        stopMonitoringServer();
        stopMessageBroker();
    }


    private boolean monitorAgentState() throws InterruptedException {
        Agent agent = new Agent();
        agent.setAgentId("agent_1");
        //agent.setUnreachableTimeout("60s")
        server.insertFact(agent);
        //blocks until first StateChangedMessage
        StateChangedMessage message = stateChangedMessages.take();
        checkFailures();
        return message.isReachable();
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
        producer.send(inputTopic, appInfo);
    }

    private void startMonitoringServer(int port) {
        ResourceMonitorServerConfiguration config =
                new ResourceMonitorServerConfiguration();
        final Resource resource = ResourceFactory.newClassPathResource(RULE_FILE, this.getClass());
        config.setDroolsResource(resource);
        config.setInputUri(inputTopic);
        config.setOutputUri(outputTopic);
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
