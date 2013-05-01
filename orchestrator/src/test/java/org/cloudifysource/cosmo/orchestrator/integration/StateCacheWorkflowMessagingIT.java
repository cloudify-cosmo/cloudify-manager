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

import com.beust.jcommander.internal.Maps;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.resource.CloudResourceProvisioner;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.cloudifysource.cosmo.statecache.RealTimeStateCacheConfiguration;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.mockito.Mockito;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Map;

/**
 * Tests integration of {@link org.cloudifysource.cosmo.statecache.StateCache} with messaging consumer.
 *
 * @author Itai Frenkel
 * @author Idan Moyal
 * @since 0.1
 */
public class StateCacheWorkflowMessagingIT {

    // message broker that isolates server
    private MessageBrokerServer broker;
    private URI inputUri;
    private MessageProducer producer;
    private RealTimeStateCache cache;
    private RuoteRuntime runtime;
    private CloudResourceProvisioner provisioner;

    @BeforeMethod
    @Parameters({ "port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        inputUri = URI.create("http://localhost:" + port + "/input/");
        producer = new MessageProducer();
        RealTimeStateCacheConfiguration config =
                new RealTimeStateCacheConfiguration();
        config.setMessageTopic(inputUri);
        cache = new RealTimeStateCache(config);
        cache.start();

        Map<String, Object> runtimeProperties = Maps.newHashMap();
        runtimeProperties.put("state_cache", cache);
        runtime = RuoteRuntime.createRuntime(runtimeProperties);
        provisioner = new CloudResourceProvisioner(Mockito.mock(CloudDriver.class), inputUri, new MessageConsumer());
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        if (cache != null)
            cache.stop();
        stopMessageBroker();
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

    @Test(timeOut = 10000)
    public void testNodeOk() {
        String flow =
            "define workflow\n" +
            "\tresource action: start_machine\n" +
            "\tstate key: \"node_1\", value: true";

        RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, runtime);
        Object wfid = workflow.asyncExecute();

        StateChangedMessage message = new StateChangedMessage();
        message.setResourceId("node_1");
        message.setReachable(true);
        producer.send(inputUri, message);

        runtime.waitForWorkflow(wfid);



        //TODO: complete test
        //ListenableFuture future = cache.waitForState();
        //future.get();
        //check node state is reachable
    }




}
