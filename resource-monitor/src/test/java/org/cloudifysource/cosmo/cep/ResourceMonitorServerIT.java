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
import org.cloudifysource.cosmo.cep.config.MockAgentConfig;
import org.cloudifysource.cosmo.cep.config.ResourceMonitorServerConfig;
import org.cloudifysource.cosmo.cep.mock.MockAgent;
import org.cloudifysource.cosmo.messaging.config.MessageBrokerServerConfig;
import org.cloudifysource.cosmo.messaging.config.MessageConsumerTestConfig;
import org.cloudifysource.cosmo.messaging.config.MessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.springframework.validation.beanvalidation.BeanValidationPostProcessor;
import org.testng.Assert;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.URI;
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
@ContextConfiguration(classes = { ResourceMonitorServerIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class ResourceMonitorServerIT extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @PropertySource("org/cloudifysource/cosmo/cep/configuration/test.properties")
    @Import({ ResourceMonitorServerConfig.class,
            MessageBrokerServerConfig.class,
            MessageConsumerTestConfig.class,
            MessageProducerConfig.class,
            MockAgentConfig.class
    })
    static class Config {
        @Bean
        public static PropertySourcesPlaceholderConfigurer propertySourcesPlaceholderConfigurer() {
            return new PropertySourcesPlaceholderConfigurer();
        }
        @Bean
        public static BeanValidationPostProcessor beanValidationPostProcessor() {
            return new BeanValidationPostProcessor();
        }
    }

    // component being tested
    @Inject
    private ResourceMonitorServer resourceMonitor;

    // receives messages from server
    @Inject
    private MessageConsumer consumer;

    // responds to agent status messages if not failed
    @Inject
    private MockAgent agent;

    @Value("${cosmo.state-cache.topic}")
    private URI stateCacheTopic;

    private BlockingQueue<StateChangedMessage> stateChangedMessages;
    private List<Throwable> failures;

    @Test(groups = "integration")
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

    @BeforeMethod(groups = "integration")
    public void startServer() {
        stateChangedMessages = Queues.newArrayBlockingQueue(100);
        failures = Lists.newCopyOnWriteArrayList();
        MessageConsumerListener<?> listener = new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                assertThat(uri).isEqualTo(stateCacheTopic);
                if (message instanceof StateChangedMessage) {
                    stateChangedMessages.add((StateChangedMessage) message);
                } else {
                    Assert.fail("Unexpected message: " + message);
                }
            }

            @Override
            public void onFailure(Throwable t) {
                failures.add(t);
            }
        };
        consumer.addListener(stateCacheTopic, listener);
    }

    private boolean monitorAgentState() throws InterruptedException {
        Agent agent = new Agent();
        agent.setAgentId("agent_1");
        resourceMonitor.insertFact(agent);
        //blocks until first StateChangedMessage

        StateChangedMessage message = null;
        while (message == null) {
            message = stateChangedMessages.poll(1, TimeUnit.SECONDS);
            validateNoFailures();
        }
        return (Boolean) message.getState().get("reachable");
    }

    private void validateNoFailures() {
        final Throwable t = Iterables.getFirst(failures, null);
        if (t != null) {
            throw Throwables.propagate(t);
        }
        agent.validateNoFailures();
    }
}
