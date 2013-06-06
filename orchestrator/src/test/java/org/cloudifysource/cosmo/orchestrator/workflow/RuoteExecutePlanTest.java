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
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.integration.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.cloudifysource.cosmo.statecache.config.RealTimeStateCacheConfig;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;
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
import java.net.URL;
import java.util.Map;

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

    @Value("${cosmo.state-cache.topic}")
    private URI stateCacheTopic;


    @Test(timeOut = 30000)
    public void testPlanExecution() throws IOException, InterruptedException {
        final String machineId = "machine";
        final String databaseId = "database";
        final RuoteWorkflow workflow = RuoteWorkflow.createFromResource(
                "ruote/pdefs/execute_plan.radial", ruoteRuntime);

        final Map<String, Object> fields = Maps.newHashMap();
        final URL dslResource = Resources.getResource("org/cloudifysource/cosmo/dsl/dsl.json");
        final String dsl = Resources.toString(dslResource, Charsets.UTF_8);
        fields.put("dsl", dsl);

        final Object wfid = workflow.asyncExecute(fields);

        Thread.sleep(100);
        messageProducer.send(stateCacheTopic, createReachableStateCacheMessage(machineId));
        messageProducer.send(stateCacheTopic, createReachableStateCacheMessage(databaseId));

        ruoteRuntime.waitForWorkflow(wfid);
    }

    private StateChangedMessage createReachableStateCacheMessage(String resourceId) {
        final StateChangedMessage message = new StateChangedMessage();
        message.setResourceId(resourceId);
        final Map<String, Object> state = Maps.newHashMap();
        state.put("reachable", "true");
        message.setState(state);
        return message;
    }

}
