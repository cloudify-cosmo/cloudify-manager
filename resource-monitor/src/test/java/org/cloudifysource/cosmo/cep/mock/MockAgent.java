package org.cloudifysource.cosmo.cep.mock;

import com.google.common.collect.Lists;
import com.google.common.collect.Queues;
import org.cloudifysource.cosmo.agent.messages.ProbeAgentMessage;
import org.cloudifysource.cosmo.cep.messages.AgentStatusMessage;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.testng.Assert;

import java.net.URI;
import java.util.List;
import java.util.concurrent.BlockingQueue;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Created with IntelliJ IDEA.
 * User: itaif
 * Date: 02/05/13
 * Time: 18:00
 * To change this template use File | Settings | File Templates.
 */
public class MockAgent {

    private final MessageConsumer consumer;
    private final URI topic;
    private boolean failed;
    private final MessageProducer producer;

    public MockAgent(final MessageProducer producer,
                     final MessageConsumer consumer,
                     final URI topic) {
        this.producer = producer;
        this.consumer = consumer;
        this.topic = topic;
    }

    public void fail() {
        this.failed = true;
    }

    public void onMessage(ProbeAgentMessage message) {
        if (!failed) {
            final AgentStatusMessage statusMessage = new AgentStatusMessage();
            statusMessage.setAgentId(message.getAgentId());
            producer.send(topic, statusMessage);
        }
    }
}
