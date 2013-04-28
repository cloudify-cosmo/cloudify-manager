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

import com.google.common.base.Function;
import com.google.common.base.Joiner;
import com.google.common.base.Preconditions;
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.cep.messages.AgentStatusMessage;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
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

/**
 * Consumes event from message broker, processes events with Drools and
 * produces new events back to message broker.
 * @author itaif
 * @since 0.1
 */
public class ResourceMonitorServer {

    private URI inputUri;
    private URI outputUri;
    private boolean pseudoClock;
    private final MessageProducer producer;
    private final MessageConsumer consumer;
    private StatefulKnowledgeSession ksession;
    private WorkingMemoryEntryPoint entryPoint;
    private final Resource droolsResource;
    private final ExecutorService executorService;
    private Future<Void> future;
    private Logger logger = LoggerFactory.getLogger(this.getClass());
    private MessageConsumerListener<AgentStatusMessage> listener;
    private KnowledgeRuntimeLogger runtimeLogger;

    public ResourceMonitorServer(ResourceMonitorServerConfiguration config) {
        inputUri = config.getInputUri();
        Preconditions.checkNotNull(inputUri);
        outputUri = config.getOutputUri();
        Preconditions.checkNotNull(outputUri);
        pseudoClock = config.isPseudoClock();
        droolsResource = config.getDroolsResource();
        Preconditions.checkNotNull(droolsResource);
        executorService = Executors.newSingleThreadExecutor();
        Preconditions.checkNotNull(executorService);
        producer = new MessageProducer();
        consumer = new MessageConsumer();
    }

    public void start() {
        initDrools();
        initEntryPoint();
        initExitChannel();
        future =
            executorService.submit(new Callable<Void>() {
                @Override
                public Void call() throws Exception {
                    ksession.fireUntilHalt();
                    return null;
                }
            });
    }

    public void stop() {
        if (listener != null) {
            consumer.removeListener(listener);
        }
        destroyDrools();
        executorService.shutdownNow();
    }

    private void initDrools() {

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
        ksession = kbase.newStatefulKnowledgeSession(sessionConfig, null);

        runtimeLogger = KnowledgeRuntimeLoggerFactory.newConsoleLogger(ksession);
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
                public void send(Object object) {
                    producer.send(outputUri, object);
                }
            };
        ksession.registerChannel("output", exitChannel);
    }

    private void initEntryPoint() {
        Collection<? extends WorkingMemoryEntryPoint> entryPoints = ksession.getWorkingMemoryEntryPoints();
        //TODO: Disable drools auto creation of entry points when it reads DRL file.
        if (entryPoints.size() > 1) {
            throw new IllegalArgumentException("DRL file must use default entry point");
        }
        entryPoint = Iterables.getOnlyElement(entryPoints);
        listener = new MessageConsumerListener<AgentStatusMessage>() {

            @Override
            public void onMessage(URI uri, AgentStatusMessage message) {
                entryPoint.insert(message);
            }

            @Override
            public void onFailure(Throwable t) {
                ResourceMonitorServer.this.onConsumerFailure(t);
            }

            @Override
            public Class<? extends AgentStatusMessage> getMessageClass() {
                return AgentStatusMessage.class;
            }
        };
        consumer.addListener(inputUri, listener);
    }

    private void onConsumerFailure(Throwable t) {
        //TODO: Replace with official info logging:
        logger.debug("Failed to consume events", t);
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
