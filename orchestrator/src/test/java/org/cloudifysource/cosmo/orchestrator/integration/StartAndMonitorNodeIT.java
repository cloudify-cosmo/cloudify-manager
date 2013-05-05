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

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.cep.Agent;
import org.cloudifysource.cosmo.cep.ResourceMonitorServer;
import org.cloudifysource.cosmo.cep.ResourceMonitorServerConfiguration;
import org.cloudifysource.cosmo.cep.mock.MockAgent;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.resource.CloudResourceProvisioner;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.cloudifysource.cosmo.statecache.RealTimeStateCacheConfiguration;
import org.drools.io.Resource;
import org.drools.io.ResourceFactory;
import org.mockito.Mockito;
import org.mockito.invocation.InvocationOnMock;
import org.mockito.stubbing.Answer;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Map;
import java.util.concurrent.ExecutionException;

import static org.mockito.Matchers.any;
import static org.mockito.Mockito.when;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class StartAndMonitorNodeIT {

    private static final String RULE_FILE = "/org/cloudifysource/cosmo/cep/AgentFailureDetector.drl";

    // message broker that isolates server
    private MessageBrokerServer broker;
    private URI inputUri;
    private RealTimeStateCache cache;
    private RuoteRuntime runtime;
    private CloudResourceProvisioner provisioner;
    private URI resourceProvisionerTopic;
    private URI stateCacheTopic;
    private URI resourceMonitorTopic;
    private URI agentTopic;
    private ResourceMonitorServer resourceMonitor;
    private CloudDriver cloudDriver;


    @Test(timeOut = 10000)
    public void testStartAndMonitor() throws ExecutionException, InterruptedException {
        final String resourceId = "node_1";

        // Create radial workflow
        final String flow =
                "define flow\n" +
                        "  resource resource_id: \"$resource_id\", action: \"start_machine\"\n" +
                        "  state resource_id: \"$resource_id\", reachable: \"true\"\n";
        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, runtime);

        // Configure mock cloud driver
        final MockAgent mockAgent = new MockAgent(agentTopic, resourceMonitorTopic);
        when(cloudDriver.startMachine(any(MachineConfiguration.class))).thenAnswer(new Answer() {
            @Override
            public Object answer(InvocationOnMock invocation) throws Throwable {
                final Agent agent = new Agent();
                agent.setAgentId(resourceId);
                resourceMonitor.insertFact(agent);
                mockAgent.start();
                return new MachineDetails(resourceId, "127.0.0.1");
            }
        });

        // Execute workflow
        final Map<String, Object> workitem = Maps.newHashMap();
        workitem.put("resource_id", resourceId);
        try {
            workflow.execute(workitem);
        } finally {
            mockAgent.stop();
        }
        mockAgent.validateNoFailures();
    }


    @BeforeMethod
    @Parameters({ "port" })
    public void startServer(@Optional("8080") int port) {
        startMessagingBroker(port);
        inputUri = URI.create("http://localhost:" + port + "/input/");
        resourceProvisionerTopic = inputUri.resolve("resource-manager");
        stateCacheTopic = inputUri.resolve("state-cache");
        resourceMonitorTopic = inputUri.resolve("resource-monitor");
        agentTopic = inputUri.resolve("agent");
        RealTimeStateCacheConfiguration config = new RealTimeStateCacheConfiguration();
        config.setMessageTopic(stateCacheTopic);
        startRealTimeStateCache(config);

        Map<String, Object> runtimeProperties = Maps.newHashMap();
        runtimeProperties.put("state_cache", cache);
        runtimeProperties.put("broker_uri", inputUri);
        runtimeProperties.put("message_producer", new MessageProducer());
        runtime = RuoteRuntime.createRuntime(runtimeProperties);
        startCloudResourceProvisioner();
        startResourceMonitor();
    }

    private void startRealTimeStateCache(RealTimeStateCacheConfiguration config) {
        cache = new RealTimeStateCache(config);
        cache.start();
    }

    private void startCloudResourceProvisioner() {
        cloudDriver = Mockito.mock(CloudDriver.class);
        provisioner = new CloudResourceProvisioner(cloudDriver, resourceProvisionerTopic);
        provisioner.start();
    }

    @AfterMethod(alwaysRun = true)
    public void stopServer() {
        stopResourceMonitor();
        stopRealTimeStateCache();
        stopCloudResourceProvisioner();
        stopMessageBroker();
    }

    private void stopRealTimeStateCache() {
        if (cache != null) {
            cache.stop();
        }
    }

    private void stopCloudResourceProvisioner() {
        if (provisioner != null) {
            provisioner.stop();
        }
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

    private void startResourceMonitor() {
        ResourceMonitorServerConfiguration config =
                new ResourceMonitorServerConfiguration();
        final Resource resource = ResourceFactory.newClassPathResource(RULE_FILE, this.getClass());
        config.setDroolsResource(resource);
        config.setResourceMonitorTopic(resourceMonitorTopic);
        config.setStateCacheTopic(stateCacheTopic);
        config.setAgentTopic(agentTopic);
        resourceMonitor = new ResourceMonitorServer(config);
        resourceMonitor.start();
    }

    private void stopResourceMonitor() {
        if (resourceMonitor != null) {
            resourceMonitor.stop();
        }
    }

}
