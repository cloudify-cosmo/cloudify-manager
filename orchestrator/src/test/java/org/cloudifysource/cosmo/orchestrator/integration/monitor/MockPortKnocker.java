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

package org.cloudifysource.cosmo.orchestrator.integration.monitor;

import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.agent.messages.ProbeAgentMessage;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.monitor.messages.AgentStatusMessage;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Runs a single dedicated thread that pings its preconfigured socket addresses
 * every second and sends a state change message of the relevant resource id once a
 * socket is successfully connected.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class MockPortKnocker implements Runnable {

    private Logger logger = LoggerFactory.getLogger(getClass());
    private static final int SLEEP_INTERVAL = 1000;
    private static final int CONNECT_TIMEOUT = 1000;

    private final URI agentTopic;
    private final MessageConsumer messageConsumer;
    private final URI resourceMonitorTopic;
    private final MessageProducer messageProducer;
    private final List<PortKnockingDescriptor> descriptors;
    private final ExecutorService executor;
    private final Map<String, AgentStatusMessage> agentStatusMessages = Maps.newConcurrentMap();

    public MockPortKnocker(URI resourceMonitorTopic,
                           URI agentTopic,
                           MessageProducer messageProducer,
                           MessageConsumer messageConsumer,
                           List<PortKnockingDescriptor> descriptors) {
        this.agentTopic = agentTopic;
        this.messageConsumer = messageConsumer;
        this.executor = Executors.newSingleThreadExecutor();
        this.resourceMonitorTopic = resourceMonitorTopic;
        this.messageProducer = messageProducer;
        this.descriptors = descriptors;
        registerForProbeMessages();
        executor.execute(this);
    }

    @Override
    public void run() {
        Thread.currentThread().setName("mock-port-knocker");
        try {
            logger.debug("Starting port knocking for [{}]", descriptors);
            doMonitor();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    public void close() {
        executor.shutdownNow();
    }

    public void doMonitor() throws Exception {
        while (!Thread.interrupted()) {
            for (Iterator<PortKnockingDescriptor> iterator = descriptors.iterator(); iterator.hasNext();) {
                PortKnockingDescriptor descriptor = iterator.next();
                boolean successfulConnection = false;
                try {
                    InetSocketAddress socketAddress = descriptor.getSocketAddress();
                    Socket socket = new Socket();
                    socket.connect(socketAddress, CONNECT_TIMEOUT);
                    logger.debug("Successfully connected to {}", descriptor.getSocketAddress());
                    successfulConnection = true;
                    try {
                        socket.close();
                    } catch (IOException e) {
                        // ignore
                    }
                } catch (Exception e) {
                    // not connected
                }
                if (successfulConnection) {
                    sendReachableStateCacheMessage(descriptor);
                    iterator.remove();
                }
            }
            Thread.sleep(SLEEP_INTERVAL);
        }
    }

    private void registerForProbeMessages() {
        messageConsumer.addListener(agentTopic, new MessageConsumerListener<ProbeAgentMessage>() {
            @Override
            public void onMessage(URI uri, ProbeAgentMessage message) {
                if (agentStatusMessages.containsKey(message.getAgentId())) {
                    AgentStatusMessage statusMessage = agentStatusMessages.get(message.getAgentId());
                    logger.debug("Received probe message: {} -> sending agent status message: {}",
                            message,
                            statusMessage);
                    messageProducer.send(resourceMonitorTopic, statusMessage);
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });
    }

    private void sendReachableStateCacheMessage(PortKnockingDescriptor descriptor) {
        final AgentStatusMessage message = new AgentStatusMessage();
        message.setAgentId(descriptor.getResourceId());
        message.getPayload().put("ip", descriptor.getSocketAddress().getHostName());
        agentStatusMessages.put(descriptor.getResourceId(), message);
    }

}
