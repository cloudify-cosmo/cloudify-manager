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
package org.cloudifysource.cosmo.monitor;

import com.google.common.base.Function;
import com.google.common.base.Joiner;
import com.google.common.collect.Iterables;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.agent.messages.ProbeAgentMessage;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.monitor.messages.AgentStatusMessage;
import org.cloudifysource.cosmo.monitor.messages.ResourceMonitorMessage;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.drools.KnowledgeBase;
import org.drools.KnowledgeBaseConfiguration;
import org.drools.KnowledgeBaseFactory;
import org.drools.builder.KnowledgeBuilder;
import org.drools.builder.KnowledgeBuilderError;
import org.drools.builder.KnowledgeBuilderFactory;
import org.drools.builder.ResourceType;
import org.drools.conf.EventProcessingOption;
import org.drools.definition.KnowledgePackage;
import org.drools.io.Resource;
import org.drools.logger.KnowledgeRuntimeLogger;
import org.drools.logger.KnowledgeRuntimeLoggerFactory;
import org.drools.runtime.Channel;
import org.drools.runtime.KnowledgeSessionConfiguration;
import org.drools.runtime.StatefulKnowledgeSession;
import org.drools.runtime.conf.ClockTypeOption;
import org.drools.runtime.rule.WorkingMemoryEntryPoint;
import org.drools.time.SessionClock;

import java.net.URI;
import java.util.Collection;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Consumes event from message broker, processes events with Drools and
 * produces new events back to message broker.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ResourceMonitorServer implements AutoCloseable {

    private final URI resourceMonitorTopic;
    private final URI stateCacheTopic;
    private final boolean pseudoClock;
    private final MessageProducer producer;
    private final MessageConsumer consumer;
    private final Resource droolsResource;
    private final ExecutorService executorService;
    private final StatefulKnowledgeSession ksession;
    private final WorkingMemoryEntryPoint entryPoint;
    private final Future<Void> future;
    private final Logger logger = LoggerFactory.getLogger(this.getClass());
    private final MessageConsumerListener<Object> listener;
    private final KnowledgeRuntimeLogger runtimeLogger;
    private final URI agentTopic;
    private final AtomicBoolean closed;
    private final Object closingLock;

    public ResourceMonitorServer(
            URI resourceMonitorTopic,
            URI stateCacheTopic,
            URI agentTopic,
            boolean pseudoClock,
            Resource droolsResource,
            MessageProducer producer,
            MessageConsumer consumer) {

        this.resourceMonitorTopic = resourceMonitorTopic;
        this.stateCacheTopic = stateCacheTopic;
        this.agentTopic = agentTopic;
        this.pseudoClock = pseudoClock;
        this.droolsResource = droolsResource;
        this.producer = producer;
        this.consumer = consumer;
        this.executorService = Executors.newSingleThreadExecutor();
        this.closed = new AtomicBoolean(false);
        this.closingLock = new Object();

        KSessionAndRuntimeLogger droolsInitProperties = initDrools();
        this.ksession = droolsInitProperties.ksession;
        this.runtimeLogger = droolsInitProperties.runtimeLogger;

        EntryPointAndListener entryPointInitProperties = initEntryPoint();
        this.entryPoint = entryPointInitProperties.entryPoint;
        this.listener = entryPointInitProperties.listener;

        initExitChannel();

        this.future = sumbitTask();

    }

    public boolean isClosed() {
        // atomic integer used instead of lock so this method does not block
        return closed.get();
    }

    /**
     */
    private static class KSessionAndRuntimeLogger {
        StatefulKnowledgeSession ksession;
        KnowledgeRuntimeLogger runtimeLogger;
    }

    /**
     */
    private static class EntryPointAndListener {
        WorkingMemoryEntryPoint entryPoint;
        MessageConsumerListener<Object> listener;
    }

    public void close() {
        // Lock needed since we want spring to wait until close really finishes
        synchronized (closingLock) {
            if (listener != null) {
                consumer.removeListener(listener);
            }
            destroyDrools();
            executorService.shutdownNow();
            closed.set(true);
        }
    }

    private KSessionAndRuntimeLogger initDrools() {

        KSessionAndRuntimeLogger result = new KSessionAndRuntimeLogger();

        KnowledgeBaseConfiguration kbaseConfig = KnowledgeBaseFactory.newKnowledgeBaseConfiguration();
        // Stream mode allows interacting with the clock (Drools Fusion)
        kbaseConfig.setOption(EventProcessingOption.STREAM);
        KnowledgeBase kbase = newKnowledgeBase(kbaseConfig);

        // start session
        KnowledgeSessionConfiguration sessionConfig = KnowledgeBaseFactory.newKnowledgeSessionConfiguration();
        if (pseudoClock) {
            sessionConfig.setOption(ClockTypeOption.get("pseudo"));
        } else {
            sessionConfig.setOption(ClockTypeOption.get("realtime"));
        }
        result.ksession = kbase.newStatefulKnowledgeSession(sessionConfig, null);

        // emits drools log entries to slf4j as org.drools.audit.WorkingMemoryConsoleLogger
        result.runtimeLogger = KnowledgeRuntimeLoggerFactory.newConsoleLogger(result.ksession);

        return result;
    }

    private KnowledgeBase newKnowledgeBase(KnowledgeBaseConfiguration config) {
        KnowledgeBase kbase = KnowledgeBaseFactory.newKnowledgeBase(config);

        KnowledgeBuilder kbuilder = KnowledgeBuilderFactory.newKnowledgeBuilder();
        // parse and compile drl
        kbuilder.add(droolsResource, ResourceType.DRL);
        if (kbuilder.hasErrors()) {
            throw toException(kbuilder.getErrors());
        }

        // add the compiled packages to a knowledgebase
        Collection<KnowledgePackage> pkgs = kbuilder.getKnowledgePackages();
        kbase.addKnowledgePackages(pkgs);
        return kbase;
    }

    private void initExitChannel() {
        Channel exitChannel = new Channel() {

            @Override
            public void send(Object message) {
                ListenableFuture future = null;
                if (message instanceof ProbeAgentMessage) {
                    future = producer.send(agentTopic, message);
                } else if (message instanceof StateChangedMessage) {
                    future = producer.send(stateCacheTopic, message);
                } else {
                    throw new IllegalStateException("Don't know how to route message " + message);
                }
                Futures.addCallback(future, new FutureCallback() {
                    @Override
                    public void onSuccess(Object result) {
                        //do nothing
                    }

                    @Override
                    public void onFailure(Throwable t) {
                        ResourceMonitorServer.this.onProducerFailure(t);
                    }
                });
            }
        };
        ksession.registerChannel("output", exitChannel);
    }

    private EntryPointAndListener initEntryPoint() {
        final EntryPointAndListener result = new EntryPointAndListener();

        Collection<? extends WorkingMemoryEntryPoint> entryPoints = ksession.getWorkingMemoryEntryPoints();
        //TODO: Disable drools auto creation of entry points when it reads DRL file.
        if (entryPoints.size() > 1) {
            throw new IllegalArgumentException("DRL file must use default entry point");
        }
        result.entryPoint = Iterables.getOnlyElement(entryPoints);
        result.listener = new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                logger.debug("Resource monitor received message [uri={}, message={}]", uri, message);
                // TODO: all message types are currently consumed here.
                // Should have a distinction between messages and tasks.
                if (message instanceof AgentStatusMessage) {
                    entryPoint.insert(message);
                } else if (message instanceof ResourceMonitorMessage) {
                    final ResourceMonitorMessage typedMessage = (ResourceMonitorMessage) message;
                    final Agent agent = new Agent();
                    agent.setAgentId(typedMessage.getResourceId());
                    insertFact(agent);
                    logger.debug("Started resource monitoring [resourceId={}]", typedMessage.getResourceId());
                }
            }

            @Override
            public void onFailure(Throwable t) {
                ResourceMonitorServer.this.onConsumerFailure(t);
            }
        };
        consumer.addListener(resourceMonitorTopic, result.listener);

        return result;
    }

    private Future<Void> sumbitTask() {
        return executorService.submit(new Callable<Void>() {
            @Override
            public Void call() throws Exception {
                try {
                    ksession.fireUntilHalt();
                } catch (Throwable t) {
                    ResourceMonitorServer.this.onDroolsFailure(t);
                    //don't leave this component in a zombie state
                    close();
                }
                return null;
            }
        });
    }


    private void onDroolsFailure(Throwable t) {
        logger.warn(MonitorLogDescription.DROOLS_ERROR, t);
    }

    private void onConsumerFailure(Throwable t) {
        logger.warn(MonitorLogDescription.MESSAGE_CONSUMER_ERROR, t);
    }

    private void onProducerFailure(Throwable t) {
        logger.warn(MonitorLogDescription.MESSAGE_PRODUCER_ERROR, t);
    }

    public void destroyDrools() {
        if (runtimeLogger != null) {
            runtimeLogger.close();
        }
        if (ksession != null) {
            ksession.halt();
            ksession.dispose();
        }
    }

    public IllegalStateException toException(Iterable<KnowledgeBuilderError> droolsErrors) {
        return new IllegalStateException("Drools errors: " +
                Joiner.on(",").join(
                        Iterables.transform(droolsErrors, new Function<KnowledgeBuilderError, String>() {
                            @Override
                            public String apply(KnowledgeBuilderError input) {
                                return input == null ? "" : input.getMessage();
                            }
                        })));
    }

    /**
     * Used by tests in order to increment pseudo clock.
     */
    public SessionClock getClock() {
        return ksession.getSessionClock();
    }

    public void insertFact(Object fact) {
        ksession.insert(fact);
    }
}
