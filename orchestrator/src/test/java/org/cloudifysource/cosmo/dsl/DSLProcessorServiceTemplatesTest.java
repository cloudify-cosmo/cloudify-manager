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
 ******************************************************************************/

package org.cloudifysource.cosmo.dsl;

import org.fest.assertions.api.Assertions;
import org.testng.annotations.Test;

import java.util.List;

/**
 * Tests multiple service templates logic of the {@link org.cloudifysource.cosmo.dsl.DSLProcessor}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessorServiceTemplatesTest extends AbstractDSLProcessorTest {

    @Test
    public void testMultipleServiceTemplates() {
        String validImportsDSLResource =
                "org/cloudifysource/cosmo/dsl/unit/service_templates/dsl-with-service-templates.yaml";
        Processed processed = process(readResource(validImportsDSLResource));
        List<Node> nodes = processed.getNodes();

        // All we care about here is verifying these nodes exists.
        // findNode fails with an exception if it cannot find the requested node
        findNode(nodes, "service_template1.host1");
        findNode(nodes, "service_template2.host1");
        findNode(nodes, "service_template3.host1");
        findNode(nodes, "service_template4.host1");

    }

    @Test
    public void testMultipleServiceTemplatesPlansOverride() {
        String validImportsDSLResource =
                "org/cloudifysource/cosmo/dsl/unit/service_templates/dsl-with-service-templates-override-plan.yaml";
        Processed processed = process(readResource(validImportsDSLResource));
        List<Node> nodes = processed.getNodes();

        // All we care about here is verifying these nodes exists.
        // findNode fails with an exception if it cannot find the requested node
        assertValidNode(findNode(nodes, "service_template1.host1"), "service_template1_host1_override");
        assertValidNode(findNode(nodes, "service_template2.host1"), "service_template2_host1_override");

    }

    private void assertValidNode(Node node, String initWorkflow) {
        Assertions.assertThat(node.getWorkflows().get("init")).isEqualTo(initWorkflow);
    }

}
