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

package org.cloudifysource.cosmo.orchestrator.integration;

import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.cep.Agent;
import org.cloudifysource.cosmo.cep.ResourceMonitorServer;
import org.cloudifysource.cosmo.cep.mock.MockAgent;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.cloudifysource.cosmo.statecache.RealTimeStateCacheConfiguration;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.cloudifysource.cosmo.statecache.StateCacheReader;
import org.cloudifysource.cosmo.statecache.StateChangeCallback;
import org.drools.io.Resource;
import org.drools.io.ResourceFactory;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;

/**
 * Tests integration of {@link org.cloudifysource.cosmo.statecache.RealTimeStateCache} with {@link
 * org.cloudifysource.cosmo.cep.ResourceMonitorServer}.
 * @author itaif
 * @since 0.1
 */
public class StateCacheResourceMonitorIT {

    private static final String RULE_FILE = "/org/cloudifysource/cosmo/cep/AgentFailureDetector.drl";
    public static final String AGENT_ID = "agent_1";
    public static final String REACHABLE_PROP = "reachable";

    // message broker that isolates server
    private MessageBrokerServer broker;

    //input for resourceMonitor and state cache
    private URI resourceMonitorTopic;
    private URI stateCacheTopic;

    //components under test
    private StateCacheReader cache;
    private ResourceMonitorServer resourceMonitor;
    private MockAgent agent;
    private URI agentTopic;


    @Test(timeOut = 10000)
    public void testNodeOk() throws InterruptedException, ExecutionException {
        Agent agent = new Agent();
        agent.setAgentId(AGENT_ID);
        resourceMonitor.insertFact(agent);

        final CountDownLatch success = new CountDownLatch(1);
        String subscriptionId = cache.subscribeToKeyValueStateChanges(null, null,
                AGENT_ID,
                new StateChangeCallback() {
                    @Override
                    public void onStateChange(Object receiver, Object context, StateCache cache,
                                              ImmutableMap<String, Object> newSnapshot) {
                        final Object entry = newSnapshot.get(AGENT_ID);
                        if (entry instanceof Map<?, ?>) {
                            final Map<?, ?> state = (Map<?, ?>) entry;
                            if (state.containsKey(REACHABLE_PROP) &&
                                    Boolean.parseBoolean(state.get(REACHABLE_PROP).toString())) {
                                success.countDown();
                            }
                        }
                    }
                });
        success.await();
        cache.removeCallback(subscriptionId);
        this.agent.validateNoFailures();
    }

    private Map<String, Object> newState() {
        Map<String, Object> state = Maps.newLinkedHashMap();
        state.put("reachable", true);
        return state;
    }


    @BeforeMethod
    @Parameters({"port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        URI uri = broker.getUri();
        stateCacheTopic = uri.resolve("state-cache");
        resourceMonitorTopic = uri.resolve("resource-monitor");
        agentTopic = uri.resolve("agent");
        startStateCache();
        startAgent();
        startResourceMonitor();

    }

    private void startAgent() {
        agent = new MockAgent(new MessageConsumer(), new MessageProducer(), agentTopic, resourceMonitorTopic);
        agent.start();
    }

    private void stopAgent() {
        agent.stop();
    }

    private void startStateCache() {
        RealTimeStateCacheConfiguration config =
                new RealTimeStateCacheConfiguration();
        config.setMessageTopic(stateCacheTopic);
        cache = new RealTimeStateCache(config);
        ((RealTimeStateCache) cache).start();
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        stopAgent();
        stopStateCache();
        stopResourceMonitor();
        stopMessageBroker();
    }

    private void stopStateCache() {
        ((RealTimeStateCache) cache).stop();
    }

    private void startMessagingBroker(int port) {
        broker = new MessageBrokerServer(port);
        broker.start();
    }

    private void stopMessageBroker() {
        if (broker != null) {
            broker.stop();
        }
    }

    private void startResourceMonitor() {
        final Resource resource = ResourceFactory.newClassPathResource(RULE_FILE, this.getClass());
        boolean pseudoClock = false;
        resourceMonitor = new ResourceMonitorServer(resourceMonitorTopic,
                stateCacheTopic,
                agentTopic,
                pseudoClock,
                resource,
                new MessageProducer(),
                new MessageConsumer());
        resourceMonitor.start();
    }

    private void stopResourceMonitor() {
        if (resourceMonitor != null) {
            resourceMonitor.stop();
        }
    }
}
