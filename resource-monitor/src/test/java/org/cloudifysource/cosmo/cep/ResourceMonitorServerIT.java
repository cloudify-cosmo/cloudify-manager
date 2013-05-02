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
import org.cloudifysource.cosmo.agent.messages.ProbeAgentMessage;
import org.cloudifysource.cosmo.cep.mock.MockAgent;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.drools.io.Resource;
import org.drools.io.ResourceFactory;
import org.drools.time.SessionPseudoClock;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Date;
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests {@link ResourceMonitorServer}.
 *
 * @author itaif
 * @since 0.1
 */

public class ResourceMonitorServerIT {

    private static final String RULE_FILE = "/org/cloudifysource/cosmo/cep/AgentFailureDetector.drl";
    private MessageConsumerListener<Object> listener;
    private BlockingQueue<StateChangedMessage> stateChangedMessages;
    private List<Throwable> failures;

    // component being tested
    private ResourceMonitorServer resourceMonitor;

    // message broker that isolates resourceMonitor
    private MessageBrokerServer broker;

    // receives messages from resourceMonitor
    private MessageConsumer consumer;

    // pushes messages to resourceMonitor
    private MessageProducer producer;

    private URI inputTopic;
    private URI outputTopic;
    private MockAgent agent;

    @Test
    public void testAgentUnreachable() throws InterruptedException {
        agent.fail();
        boolean reachable = monitorAgentState();
        assertThat(reachable).isFalse();
    }

    @Test
    public void testAgentReachable() throws InterruptedException {
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
        agent = new MockAgent(producer, consumer, inputTopic);
        startResourceMonitor();
        stateChangedMessages = Queues.newArrayBlockingQueue(100);
        failures = Lists.newCopyOnWriteArrayList();
        listener = new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                assertThat(uri).isEqualTo(outputTopic);
                if (message instanceof StateChangedMessage) {
                    stateChangedMessages.add((StateChangedMessage) message);
                } else if (message instanceof ProbeAgentMessage) {
                    ResourceMonitorServerIT.this.agent.onMessage((ProbeAgentMessage) message);
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
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        consumer.removeListener(listener);
        stopResourceMonitor();
        stopMessageBroker();
    }


    private boolean monitorAgentState() throws InterruptedException {
        Agent agent = new Agent();
        agent.setAgentId("agent_1");
        //agent.setUnreachableTimeout("60s")
        resourceMonitor.insertFact(agent);
        //blocks until first StateChangedMessage

        StateChangedMessage message = null;
        while (message == null) {
            message = stateChangedMessages.poll(1, TimeUnit.SECONDS);
            checkFailures();
        }
        return (Boolean) message.getState().get("reachable");
    }

    private void checkFailures() {
        final Throwable t = Iterables.getFirst(failures, null);
        if (t != null) {
            throw Throwables.propagate(t);
        }
    }

    private SessionPseudoClock getClock() {
        return ((SessionPseudoClock) resourceMonitor.getClock());
    }

    private void startResourceMonitor() {
        ResourceMonitorServerConfiguration config =
                new ResourceMonitorServerConfiguration();
        final Resource resource = ResourceFactory.newClassPathResource(RULE_FILE, this.getClass());
        config.setDroolsResource(resource);
        config.setInputUri(inputTopic);
        config.setOutputUri(outputTopic);
        resourceMonitor = new ResourceMonitorServer(config);
        resourceMonitor.start();
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

    private void stopResourceMonitor() {
        if (resourceMonitor != null) {
            resourceMonitor.stop();
        }
    }

    private Date now() {
        return new Date(getClock().getCurrentTime());
    }
}
