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

import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.tasks.EventListener;
import org.cloudifysource.cosmo.tasks.TaskExecutor;
import org.jruby.embed.InvokeFailedException;
import org.mockito.invocation.InvocationOnMock;
import org.mockito.stubbing.Answer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URISyntaxException;
import java.util.Map;

import static org.mockito.Matchers.any;
import static org.mockito.Matchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;

/**
 * Tests ruote "execute task" participant when producer raises exception.
 *
 * @author itaif
 * @since 0.1
 */

@ContextConfiguration(classes = { RuoteExecuteFailedTaskParticipantTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RuoteExecuteFailedTaskParticipantTest extends AbstractTestNGSpringContextTests {

    /**
     * Test configuration.
     */
    @Configuration
    @PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
    static class Config extends TestConfig {

        @Bean
        public TaskExecutor executor() throws IOException {
            final TaskExecutor taskExecutor = mock(TaskExecutor.class);
            doAnswer(new Answer<Void>() {
                @Override
                public Void answer(InvocationOnMock invocation) throws Throwable {
                    throw new Exception("Failed sending task");
                }
            })
                    .when(taskExecutor)
                    .sendTask(anyString(), anyString(), anyString(), anyString(),
                            any(EventListener.class));
            return taskExecutor;
        }

        @Bean
        public RuoteRuntime ruoteRuntime() {
            Map<String, Object> runtimeProperties = Maps.newHashMap();
            runtimeProperties.put("executor", executor);
            return RuoteRuntime.createRuntime(runtimeProperties);
        }

        @Inject
        private TaskExecutor executor;

    }

    @Inject
    private RuoteRuntime runtime;


    @Test(timeOut = 30000, expectedExceptions = { InvokeFailedException.class })
    public void testFailedTaskExecution() throws URISyntaxException, InterruptedException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", exec: \"%s\", payload: {\n" +
                "    resource_id: \"%s\"\n" +
                "  }\n", target, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);
        final Object id = workflow.asyncExecute();
        runtime.waitForWorkflow(id);
    }

    @Test(timeOut = 30000)
    public void testIgnoredFailedTaskExecution() throws URISyntaxException, InterruptedException {

        final String target = "http://localhost:8080/";
        final String resourceId = "vm_node";
        final String execute = "start_machine";

        final String radial = String.format("define start_node\n" +
                "  execute_task target: \"%s\", exec: \"%s\", payload: {\n" +
                "    resource_id: \"%s\"\n" +
                "  }, on_error: do_nothing\n" +
                "  define do_nothing\n" +
                "    echo nop\n",
                target, execute, resourceId);

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(radial, runtime);
        final Object id = workflow.asyncExecute();
        runtime.waitForWorkflow(id);
    }

}
