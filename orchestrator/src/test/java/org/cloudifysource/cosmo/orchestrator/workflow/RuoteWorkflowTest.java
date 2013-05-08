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

import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RuoteWorkflowTest {

    @BeforeMethod
    public void before() {
        RuoteJavaParticipant.reset();
    }

    @Test
    public void testWorkflowExecution() {
        final RuoteRuntime runtime = RuoteRuntime.createRuntime();
        Workflow workflow = RuoteWorkflow.createFromResource("workflows/radial/java_workflow.radial", runtime);
        workflow.execute();
        assertThat(RuoteJavaParticipant.get()).isEqualTo(3);
    }

    @Test
    public void testWorkflowPayloadParameter() {
        final RuoteRuntime runtime = RuoteRuntime.createRuntime();
        final String radial =
                "define flow\n" +
                        "  execute_task topic: \"the_topic\", payload: { a: '111', b: '222' }\n";
        Workflow workflow = RuoteWorkflow.createFromString(radial, runtime);
        workflow.execute();
    }

}
