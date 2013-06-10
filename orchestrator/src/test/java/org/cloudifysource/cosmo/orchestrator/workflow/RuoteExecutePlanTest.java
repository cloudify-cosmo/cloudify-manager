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

package org.cloudifysource.cosmo.orchestrator.workflow;

import com.google.common.base.Charsets;
import com.google.common.base.Optional;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.dsl.DSLProcessor;
import org.cloudifysource.cosmo.dsl.PluginArtifactAwareDSLPostProcessor;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.ruote.RuoteRadialVariable;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.cloudifysource.cosmo.statecache.config.RealTimeStateCacheConfig;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
import org.cloudifysource.cosmo.tasks.messages.ExecuteTaskMessage;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

/**
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { RuoteExecutePlanTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RuoteExecutePlanTest extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @Import({
            MockMessageConsumerConfig.class,
            MockMessageProducerConfig.class,
            RealTimeStateCacheConfig.class,
            RuoteRuntimeConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private RuoteRuntime ruoteRuntime;

    @Inject
    private RealTimeStateCache stateCache;

    @Inject
    private MessageProducer messageProducer;

    @Inject
    private MessageConsumer messageConsumer;

    @Value("${cosmo.state-cache.topic}")
    private URI stateCacheTopic;


    @Test(timeOut = 30000)
    public void testPlanExecution() throws IOException, InterruptedException {
        final String machineId = "mysql_machine";
        final String databaseId = "mysql_database_server";
        final RuoteWorkflow workflow = RuoteWorkflow.createFromResource(
                "ruote/pdefs/execute_plan.radial", ruoteRuntime);

        final Map<String, Object> fields = Maps.newHashMap();
        final String dsl = getResourceAsString("org/cloudifysource/cosmo/dsl/dsl.json");
        fields.put("dsl", dsl);

        final Object wfid = workflow.asyncExecute(fields);

        Thread.sleep(100);
        messageProducer.send(stateCacheTopic, createReachableStateCacheMessage(machineId));
        messageProducer.send(stateCacheTopic, createReachableStateCacheMessage(databaseId));

        final CountDownLatch latch = new CountDownLatch(5);

        messageConsumer.addListener(URI.create("provisioner_plugin"),
                new PluginExecutionMessageConsumerListener(latch, new String[] {"create", "start"}));
        messageConsumer.addListener(URI.create("configurer_plugin"),
                new PluginExecutionMessageConsumerListener(latch, new String[] {"install", "start"}));
        messageConsumer.addListener(URI.create("schema_configurer_plugin"),
                new PluginExecutionMessageConsumerListener(latch, new String[] {"create"}));

        ruoteRuntime.waitForWorkflow(wfid);
        latch.await();
    }



    @Test(timeOut = 30000)
    public void testExecuteOperation() throws URISyntaxException, InterruptedException {
        final String operation = "test";
        final Map<String, Object> props = Maps.newHashMap();
        props.put("message_consumer", messageConsumer);
        props.put("message_producer", messageProducer);
        final Map<String, Object> variables = Maps.newHashMap();
        final String executePlanRadial = getResourceAsString("ruote/pdefs/execute_operation.radial");
        variables.put("execute_operation", new RuoteRadialVariable(executePlanRadial));
        final RuoteRuntime runtime = RuoteRuntime.createRuntime(props, variables);
        final String radial = "define flow\n" +
                "  execute_operation operation: '" + operation + "'\n";

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);
        final Map<String, Object> fields = Maps.newHashMap();
        final Map<String, Object> node = Maps.newHashMap();
        final Map<String, Object> operations = Maps.newHashMap();
        final String plugin = "some-plugin";
        operations.put(operation, plugin);
        node.put("operations", operations);
        fields.put("node", node);

        final CountDownLatch latch = new CountDownLatch(1);

        messageConsumer.addListener(new URI(plugin),
                new PluginExecutionMessageConsumerListener(latch, new String[] {operation}));

        workflow.execute(fields);

        latch.await();
    }

    private String getResourceAsString(String resourceName) {
        final URL resource = Resources.getResource(resourceName);
        try {
            return Resources.toString(resource, Charsets.UTF_8);
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    private StateChangedMessage createReachableStateCacheMessage(String resourceId) {
        final StateChangedMessage message = new StateChangedMessage();
        message.setResourceId(resourceId);
        final Map<String, Object> state = Maps.newHashMap();
        state.put("reachable", "true");
        message.setState(state);
        return message;
    }

    private static class PluginExecutionMessageConsumerListener
            implements MessageConsumerListener<ExecuteTaskMessage> {
        private CountDownLatch latch;
        private String[] operations;
        PluginExecutionMessageConsumerListener(CountDownLatch latch, String[] operations) {
            this.latch = latch;
            this.operations = operations;
        }
        public void onMessage(URI uri, ExecuteTaskMessage message) {
            final Optional<Object> exec = message.getPayloadProperty("exec");
            if (!exec.isPresent()) {
                return;
            }
            String actualOperation = exec.get().toString();
            for (String expectedOperation : operations) {
                if (actualOperation.equals(expectedOperation)) {
                    latch.countDown();
                    break;
                }
            }
        }
        public void onFailure(Throwable t) {
        }
    }

}
