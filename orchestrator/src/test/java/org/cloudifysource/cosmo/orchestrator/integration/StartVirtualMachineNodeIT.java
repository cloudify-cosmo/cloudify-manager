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

import com.google.common.base.Charsets;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import com.google.common.io.Files;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.monitor.ResourceMonitorServer;
import org.cloudifysource.cosmo.monitor.config.ResourceMonitorServerConfig;
import org.cloudifysource.cosmo.monitor.mock.MockAgent;
import org.cloudifysource.cosmo.cloud.driver.config.VagrantCloudDriverConfig;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MessageBrokerServerConfig;
import org.cloudifysource.cosmo.messaging.config.MessageConsumerTestConfig;
import org.cloudifysource.cosmo.messaging.config.MessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.orchestrator.recipe.JsonRecipe;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.provisioner.config.CloudResourceProvisionerConfig;
import org.cloudifysource.cosmo.statecache.config.RealTimeStateCacheConfig;
import org.cloudifysource.cosmo.tasks.messages.TaskStatusMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

/**
 * An integration test combining the following components:
 *  1. JSON recipe.
 *  2. Ruote workflow.
 *  3. Vagrant cloud driver.
 *  4. Message Broker.
 *  5. Real time state cache.
 *  6. Drools.
 *
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { StartVirtualMachineNodeIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class StartVirtualMachineNodeIT extends AbstractTestNGSpringContextTests {


    /**
     * Test configuration.
     */
    @Configuration
    @Import({
            RealTimeStateCacheConfig.class,
            CloudResourceProvisionerConfig.class,
            ResourceMonitorServerConfig.class,
            MessageBrokerServerConfig.class,
            MessageConsumerTestConfig.class,
            MessageProducerConfig.class,
            RuoteRuntimeConfig.class,
            VagrantCloudDriverConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private RuoteRuntime runtime;

    @Inject
    private ResourceMonitorServer resourceMonitor;

    @Inject
    private MessageProducer messageProducer;

    @Inject
    private MessageConsumer messageConsumer;

    @Value("${cosmo.message-broker.uri}")
    private URI inputUri;

    @Value("${cosmo.resource-provisioner.topic}")
    private String resourceProvisionerTopic;

    @Value("${cosmo.resource-monitor.topic}")
    private URI resourceMonitorTopic;

    @Value("${cosmo.agent.topic}")
    private URI agentTopic;

    private static final String RECIPE_PATH = "recipes/json/tomcat/vm_node_recipe.json";
    private MockAgent mockAgent;

    @AfterMethod
    public void afterMethod() {
        if (mockAgent != null) {
            mockAgent.close();
        }
    }

    @Test(groups = "vagrant", timeOut = 30000 * 2 * 5)
    public void testStartVirtualMachine() throws ExecutionException, InterruptedException, URISyntaxException {
        final JsonRecipe recipe = JsonRecipe.load(readRecipe());
        final List<String> nodes = recipe.getNodes();
        final String resourceId = nodes.get(0);
        final Map<String, Object> resource = recipe.get(resourceId).get();
        final List<?> workflows = (List<?>) resource.get("workflows");
        final String workflowName = workflows.get(0).toString();
        final String workflow = loadWorkflow(resourceId, workflowName);
        final RuoteWorkflow ruoteWorkflow = RuoteWorkflow.createFromString(workflow, runtime);

        messageConsumer.addListener(new URI(resourceProvisionerTopic), new MessageConsumerListener<Object>() {
            @Override
            public void onMessage(URI uri, Object message) {
                if (message instanceof TaskStatusMessage) {
                    mockAgent = new MockAgent(messageConsumer, messageProducer, agentTopic, resourceMonitorTopic);
                }
            }
            @Override
            public void onFailure(Throwable t) {
                t.printStackTrace();
            }
        });

        // Execute workflow
        final Map<String, Object> workitem = Maps.newHashMap();
        workitem.put("resource_id", resourceId);
        workitem.put("resource_provisioner", resourceProvisionerTopic);
        ruoteWorkflow.execute(workitem);
    }

    private String loadWorkflow(String resourceId, String workflowName) {
        final String workflowFileName = String.format("%s_%s.radial", resourceId, workflowName);
        final String parentDirectory = new File(Resources.getResource(RECIPE_PATH).getPath()).getParent();
        final File file = new File(parentDirectory, workflowFileName);
        Preconditions.checkArgument(file.exists());
        try {
            return Files.toString(file, Charsets.UTF_8);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private String readRecipe() {
        final URL resource = Resources.getResource(RECIPE_PATH);
        try {
            return Resources.toString(resource, Charsets.UTF_8);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

}
