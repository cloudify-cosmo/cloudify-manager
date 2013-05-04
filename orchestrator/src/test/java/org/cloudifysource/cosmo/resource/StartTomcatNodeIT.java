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

import com.google.common.base.Charsets;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;
import com.google.common.io.Files;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.vagrant.VagrantCloudDriver;
import org.cloudifysource.cosmo.messaging.broker.MessageBrokerServer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.recipe.JsonRecipe;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.statecache.DefaultStateCacheReader;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class StartTomcatNodeIT {

    private MessageBrokerServer broker;
    private MessageProducer producer;
    private URI uri;
    private String key = "resource-manager";
    private CloudDriver driver;
    private File vagrantRoot;
    private CloudResourceProvisioner provisioner;
    private StateCache stateCache;
    private DefaultStateCacheReader stateCacheReader;

    @BeforeMethod(alwaysRun = true, groups = "vagrant")
    @Parameters({ "port" })
    public void startMessageBrokerServer(@Optional("8080") int port) {
        broker = new MessageBrokerServer();
        broker.start(port);
        producer = new MessageProducer();
        uri = URI.create("http://localhost:" + port);
        vagrantRoot = Files.createTempDir();
        driver = new VagrantCloudDriver(vagrantRoot);
        URI cloudResourceUri = uri.resolve("/" + key);
        provisioner = new CloudResourceProvisioner(driver, cloudResourceUri);
        provisioner.start();
        stateCache = new StateCache.Builder().build();
        stateCacheReader = new DefaultStateCacheReader(stateCache);
    }

    @AfterMethod(alwaysRun = true, groups = "vagrant")
    public void stopMessageBrokerServer() {
        if (driver != null)
            driver.terminateMachines();
        if (provisioner != null)
            provisioner.stop();
        vagrantRoot.delete();
        if (broker != null) {
            broker.stop();
        }
    }

    @Test(groups = "vagrant")
    public void testStartTomcatNode() throws IOException {
        // Load recipe
        URL url = Resources.getResource("recipes/json/tomcat/tomcat_node_recipe.json");
        String json = Resources.toString(url, Charsets.UTF_8);
        JsonRecipe recipe = JsonRecipe.load(json);
        Map<String, Object> node = recipe.get("tomcat_node").get();
        List<?> resources = (List<?>) node.get("resources");

        // Create ruote runtime
        final Map<String, Object> properties = Maps.newHashMap();
        properties.put("message_producer", producer);
        properties.put("broker_uri", uri);
        properties.put("state_cache", stateCacheReader);
        final RuoteRuntime ruoteRuntime = RuoteRuntime.createRuntime(properties);

        // Create ruote workflow
        final File recipeFile = new File(url.getPath());
        final String workflowName = "start_node";
        final File workflowFile = new File(recipeFile.getParent(), workflowName + ".radial");
        Preconditions.checkArgument(workflowFile.exists());
        final RuoteWorkflow workflow = RuoteWorkflow.createFromFile(workflowFile.getAbsolutePath(), ruoteRuntime);

        // Execute workflow
        Map<String, Object> workitemFields = Maps.newHashMap();
        workitemFields.put("id", "tomcat_node");
        workitemFields.put("resources", resources);

        Object wfid = workflow.asyncExecute(workitemFields);

        stateCache.put("vm", "ready");
        stateCache.put("tomcat", "ready");

        ruoteRuntime.waitForWorkflow(wfid);
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
