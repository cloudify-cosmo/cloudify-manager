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

package org.cloudifysource.cosmo.cep.mock;

import com.google.common.base.Throwables;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.agent.messages.ProbeAgentMessage;
import org.cloudifysource.cosmo.cep.messages.AgentStatusMessage;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.testng.Assert;

import java.net.URI;
import java.util.List;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Mocks the behavior of a real agent.
 *
 * @author itaif
 * @since 0.1
 */
public class MockAgent implements AutoCloseable {

    private boolean failed;
    private final MessageProducer producer;
    private final MessageConsumer consumer;
    private final URI requestTopic;
    private final URI responseTopic;
    private final MessageConsumerListener<Object> listener;
    private final List<Throwable> failures;

    public MockAgent(final MessageConsumer consumer,
                     final MessageProducer producer,
                     final URI agentTopic,
                     final URI resourceMonitorTopic) {
        this.consumer = consumer;
        this.producer = producer;
        this.requestTopic = agentTopic;
        this.responseTopic = resourceMonitorTopic;
        this.failures = Lists.newArrayList();
        this.listener = new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                assertThat(uri).isEqualTo(agentTopic);
                if (message instanceof ProbeAgentMessage) {
                    onProbeAgentMessage((ProbeAgentMessage) message);
                } else {
                    Assert.fail("Unexpected message: " + message);
                }
            }

            @Override
            public void onFailure(Throwable t) {
                failures.add(t);
            }
        };
        this.consumer.addListener(requestTopic, listener);
    }

    public void close() {
        consumer.removeListener(listener);
    }

    public void validateNoFailures() {
        final Throwable t = Iterables.getFirst(failures, null);
        if (t != null) {
            throw Throwables.propagate(t);
        }
    }

    public void fail() {
        this.failed = true;
    }

    public void onProbeAgentMessage(ProbeAgentMessage message) {
        if (!failed) {
            final AgentStatusMessage statusMessage = new AgentStatusMessage();
            statusMessage.setAgentId(message.getAgentId());
            producer.send(responseTopic, statusMessage);
        }
    }
}
