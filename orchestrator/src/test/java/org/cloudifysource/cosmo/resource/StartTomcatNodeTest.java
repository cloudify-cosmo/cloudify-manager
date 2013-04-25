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
package org.cloudifysource.cosmo.resource;

import com.beust.jcommander.internal.Maps;
import com.google.common.base.Charsets;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.io.Files;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.vagrant.VagrantCloudDriver;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.recipe.JsonRecipe;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class StartTomcatNodeTest {

    private MessageBrokerServer broker;
    private MessageConsumer consumer;
    private MessageProducer producer;
    private URI uri;
    private String key = "resource-manager";
    private CloudDriver driver;
    private File vagrantRoot;

    @BeforeMethod(alwaysRun = true)
    @Parameters({ "port" })
    public void startMessageBrokerServer(@Optional("8080") int port) {
        broker = new MessageBrokerServer();
        broker.start(port);
        consumer = new MessageConsumer();
        producer = new MessageProducer();
        uri = URI.create("http://localhost:" + port);
        vagrantRoot = Files.createTempDir();
        driver = new VagrantCloudDriver(vagrantRoot);
    }

    @AfterMethod(alwaysRun = true)
    public void stopMessageBrokerServer() {
        driver.terminateMachines();
        vagrantRoot.delete();
        consumer.removeAllListeners();
        if (broker != null) {
            broker.stop();
        }
    }

    @Test(groups = "vagrant")
    public void testStartTomcatNode() throws IOException {
        URI resourceProvisioningUri = uri.resolve("/" + key);
        final CloudResourceManager manager =
                new CloudResourceManager(driver, resourceProvisioningUri, consumer);
        URL url = Resources.getResource("recipes/json/tomcat/recipe.json");
        String json = Resources.toString(url, Charsets.UTF_8);
        JsonRecipe recipe = JsonRecipe.load(json);
        assertThat(recipe.get("tomcat_node").isPresent()).isTrue();
        startWorkflow(new File(url.getPath()).getParentFile().getPath(), recipe, "tomcat_node", "start_node");
        repetitiveAssert(new Runnable() {
            @Override
            public void run() {
                assertThat(manager.isMachineStarted()).isTrue();
            }
        }, 3, TimeUnit.MINUTES);
    }

    private void startWorkflow(String recipePath, JsonRecipe recipe, String name, String workflowName) {
        try {
            final Map<String, Object> properties = Maps.newHashMap();
            properties.put("message_producer", producer);
            properties.put("broker_uri", uri);
            final RuoteRuntime ruoteRuntime = RuoteRuntime.createRuntime(properties);
            final File workflowFile = new File(recipePath, workflowName + ".radial");
            Preconditions.checkArgument(workflowFile.exists());
            final RuoteWorkflow workflow = RuoteWorkflow.createFromFile(workflowFile.getAbsolutePath(), ruoteRuntime);
            workflow.execute();
        } catch (Exception e) {
            Throwables.propagate(e);
        }
    }

    public static void repetitiveAssert(Runnable runnable, long timeout, TimeUnit timeUnit) {
        long timeoutMillis = timeUnit.toMillis(timeout);
        long deadlineTime = System.currentTimeMillis() + timeoutMillis;
        boolean success = false;
        while (!success && System.currentTimeMillis() < deadlineTime) {
            try {
                runnable.run();
                success = true;
            } catch (Throwable t) {
                try {
                    Thread.sleep(10);
                } catch (InterruptedException e) {
                }
            }
        }
        if (!success)
            runnable.run();
    }
}
