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
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.orchestrator.workflow.config.RuoteRuntimeConfig;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.tasks.MockCeleryTaskWorker;
import org.cloudifysource.cosmo.tasks.TaskReceivedListener;
import org.cloudifysource.cosmo.tasks.config.MockCeleryTaskWorkerConfig;
import org.cloudifysource.cosmo.tasks.config.MockTaskExecutorConfig;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.fest.assertions.api.Assertions;
import org.jruby.embed.InvokeFailedException;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.net.URISyntaxException;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests ruote "execute task" participant.
 *
 * @author Idan Moyal
 * @since 0.1
 */

@ContextConfiguration(classes = { RuoteExecuteTaskParticipantTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RuoteExecuteTaskParticipantTest extends AbstractTestNGSpringContextTests {

    /**
     * Test configuration.
     */
    @Configuration
    @Import({
            StateCacheConfig.class,
            RuoteRuntimeConfig.class,
            TemporaryDirectoryConfig.class,
            MockTaskExecutorConfig.class,
            MockCeleryTaskWorkerConfig.class
    })
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {
    }

    @Inject
    private RuoteRuntime runtime;

    @Inject
    private MockCeleryTaskWorker worker;

    /**
     * Scenario 1:
     *   1.
     * @throws URISyntaxException
     * @throws InterruptedException
     */
    @Test(timeOut = 30000)
    public void testTaskExecution() throws URISyntaxException, InterruptedException {
        final String resourceId = "vm_node";
        final String execute = "start_machine";
        final CountDownLatch latch = new CountDownLatch(1);

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", exec: \"%s\", payload: {\n" +
                "       properties: {\n" +
                "           resource_id: \"%s\"\n" +
                "       }\n" +
                "  }\n", "http://localhost:8080/", execute, resourceId);


        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        worker.addListener("http://localhost:8080/", new TaskReceivedListener() {

            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                boolean valid = Objects.equal(target, "http://localhost:8080/");
                valid &= Objects.equal(taskName, execute);
                valid &= Objects.equal(kwargs.get("resource_id"), resourceId);
                if (valid) {
                    latch.countDown();
                }
                return null;
            }
        });


        final Object id = workflow.asyncExecute();
        latch.await();
        runtime.waitForWorkflow(id);
    }

    @Test(timeOut = 30000, expectedExceptions = { InvokeFailedException.class })
    public void testTaskExecutionFailure() throws Exception {
        final String resourceId = "vm_node";
        final String execute = "start_machine";

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", exec: \"%s\", payload: {\n" +
                "    resource_id: \"%s\",\n" +
                "    properties: {\n" +
                "      fail: \"%s\"\n" +
                "    }\n" +
                "  }\n", "http://localhost:8080/", execute, resourceId, true);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);

        final Object id = workflow.asyncExecute();
        runtime.waitForWorkflow(id);
        Assertions.fail("Exception expected!");
    }

    @Test(timeOut = 30000)
    public void testTaskExecutionResult() {
        RuoteJavaParticipant.reset();
        worker.addListener("task_target", new TaskReceivedListener() {
            @Override
            public Object onTaskReceived(String target, String taskName, Map<String, Object> kwargs) {
                // do nothing..
                return "mockResult";
            }
        });
        final String radial = "define start_node\n" +
                "  execute_task target: 'task_target', exec: 'some_method', to_f: 'result', payload: {\n" +
                "    resource_id: 'some_id'\n" +
                "  }\n" +
                "  java class: 'org.cloudifysource.cosmo.orchestrator.workflow.RuoteJavaParticipant'\n";

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);
        final Object id = workflow.asyncExecute();
        runtime.waitForWorkflow(id);

        final Map<String, Object> workitemFields = RuoteJavaParticipant.getWorkitemFields();
        assertThat(workitemFields).containsKey("result");
        assertThat(workitemFields.get("result")).isEqualTo("mockResult");
    }

}
