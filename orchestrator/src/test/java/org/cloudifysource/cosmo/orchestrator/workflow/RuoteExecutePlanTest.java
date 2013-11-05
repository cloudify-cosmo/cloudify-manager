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

import com.google.common.base.Objects;
import com.google.common.base.Preconditions;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.orchestrator.workflow.config.DefaultRuoteWorkflowConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.cloudifysource.cosmo.statecache.StateCacheValue;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.tasks.MockCeleryTaskWorker;
import org.cloudifysource.cosmo.tasks.TaskReceivedListener;
import org.cloudifysource.cosmo.tasks.config.MockCeleryTaskWorkerConfig;
import org.cloudifysource.cosmo.tasks.config.MockTaskExecutorConfig;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;


/**
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { RuoteExecutePlanTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RuoteExecutePlanTest extends AbstractTestNGSpringContextTests {

    private static final String CLOUDIFY_MANAGEMENT = "cloudify.management";
    protected Logger logger = LoggerFactory.getLogger(this.getClass());

    /**
     */
    @Configuration
    @Import({
            DefaultRuoteWorkflowConfig.class,
            RuoteRuntimeConfig.class,
            TemporaryDirectoryConfig.class,
            MockTaskExecutorConfig.class,
            MockCeleryTaskWorkerConfig.class,
            StateCacheConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private RuoteRuntime ruoteRuntime;

    @Inject
    private RuoteWorkflow ruoteWorkflow;

    @Inject
    private StateCache stateCache;

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @Inject
    private MockCeleryTaskWorker worker;



    @Test(timeOut = 30000)
    public void testRuntimePropertiesInjection() throws IOException, InterruptedException {
        final String dslFile = "org/cloudifysource/cosmo/dsl/dsl-with-base-imports.yaml";
        final String machineId = "mysql_template.mysql_host";
        final String ip = "10.0.0.1";

        Map<String, Object> fields = Maps.newHashMap();
        fields.put("dsl", Resources.getResource(dslFile).getFile());
        ruoteWorkflow.asyncExecute(fields);

        final CountDownLatch latch = new CountDownLatch(1);

        worker.addListener(CLOUDIFY_MANAGEMENT, new TaskReceivedListener() {
            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                if (taskName.endsWith("multi_instance_plan")) {
                    return kwargs.get("plan");
                }
                return null;
            }
        });

        worker.addListener(machineId, new TaskReceivedListener() {
            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {

                if (taskName.endsWith("verify_plugin")) {
                    return "True";
                }

                Map<?, ?> runtimeProperties = (Map<?, ?>) kwargs.get("cloudify_runtime");
                if (runtimeProperties.containsKey(machineId)) {
                    Map<?, ?> machineProperties = (Map<?, ?>) runtimeProperties.get(machineId);
                    if (Objects.equal(ip, machineProperties.get("ip"))) {
                        latch.countDown();
                    }
                }
                return null;
            }
        });

        discoveredIpAddress(machineId, ip);
        reachable(machineId);
        latch.await();
    }

    @Test(timeOut = 60000)
    public void testExecuteOperationFailure() {
        String radial = "define workflow\n" +
                "  execute_operation operation: 'op'";

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, ruoteRuntime);
        Map<String, Object> plugin = Maps.newHashMap();
        plugin.put("agent_plugin", "true");
        Map<String, Object> plugins = Maps.newHashMap();
        plugins.put("plugin", plugin);
        Map<String, Object> operations = Maps.newHashMap();
        operations.put("op", "plugin");
        Map<String, Object> node = Maps.newHashMap();
        node.put("id", "id");
        node.put("host_id", "host");
        node.put("operations", operations);
        node.put("plugins", plugins);
        node.put("properties", Maps.newHashMap());
        Map<String, Object> fields = Maps.newHashMap();
        fields.put("node", node);
        fields.put("plan", Maps.newHashMap());

        final AtomicInteger counter = new AtomicInteger(0);
        TaskReceivedListener listener = new TaskReceivedListener() {
            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                System.out.println(
                        "-- " + counter.get() + " received task: " + target + ", " + taskName + ", " + kwargs);
                if (taskName.contains("verify_plugin")) {
                    if (counter.get() < 2) {
                        counter.incrementAndGet();
                        return "False";
                    }
                }
                return "True";
            }
        };

        worker.addListener("host", listener);

        Object wfid = workflow.asyncExecute(fields);
        ruoteRuntime.waitForWorkflow(wfid);
    }


    private void reachable(String nodeId) {
        Preconditions.checkNotNull(nodeId);
        stateCache.put(nodeId, "reachable", new StateCacheValue("true"));
    }

    private void discoveredIpAddress(String nodeId, String ipAddress) {
        Preconditions.checkNotNull(nodeId);
        Preconditions.checkNotNull(ipAddress);
        stateCache.put(nodeId, "ip", new StateCacheValue(ipAddress));
    }
}
