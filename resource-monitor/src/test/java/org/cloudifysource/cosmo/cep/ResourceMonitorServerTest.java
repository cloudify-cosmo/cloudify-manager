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
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServerConfiguration;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerConfiguration;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducerConfiguration;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.drools.time.SessionPseudoClock;
import org.springframework.beans.factory.annotation.Value;
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
@ContextConfiguration(classes = { ResourceMonitorServerTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class ResourceMonitorServerTest extends AbstractTestNGSpringContextTests {

    /**
     * @author Dan Kilman
     * @since 0.1
     */
    @Configuration
    @PropertySource("org/cloudifysource/cosmo/cep/configuration/test.properties")
    @Import({ ResourceMonitorServerConfiguration.class,
            MessageBrokerServerConfiguration.class,
            MessageConsumerConfiguration.class,
            MessageProducerConfiguration.class
    })
    static class Config { }

    @Value("${resource.monitor.port}")
    private int port;

    @Value("${agent.id}")
    private String agentId;

    @Value("${input.uri}")
    private URI inputTopic;

    @Value("${output.uri}")
    private URI outputTopic;

    // component being tested
    @Inject
    private ResourceMonitorServer server;

    // message broker that isolates server
    @Inject
    private MessageBrokerServer broker;

    // receives messages from server
    @Inject
    private MessageConsumer consumer;

    // pushes messages to server
    @Inject
    private MessageProducer producer;

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

    @BeforeMethod(groups = "integration")
    public void startServer() {
        startMessagingBroker();
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
        startMonitoringServer();
    }

    private void mockAgent(ProbeAgentMessage message) {
        if (!mockAgentFailed) {
            final AgentStatusMessage statusMessage = new AgentStatusMessage();
            statusMessage.setAgentId(agentId);
            producer.send(inputTopic, statusMessage);
        }
    }

    @AfterMethod(alwaysRun = true, groups = "integration")
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

    private void startMonitoringServer() {
        server.start();
    }

    private void startMessagingBroker() {
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
