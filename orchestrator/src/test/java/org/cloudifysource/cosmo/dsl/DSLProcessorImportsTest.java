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
import org.testng.Assert;
import org.testng.annotations.Test;

import java.util.List;

/**
 * Tests the import mechanism of the {@link DSLProcessor}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessorImportsTest extends AbstractDSLProcessorTest {

    @Test
    public void testValidImports() {

        String validImportsDSLResource = "org/cloudifysource/cosmo/dsl/unit/imports/valid/dsl-with-imports.yaml";

        Processed processed = process(readResource(validImportsDSLResource));

        List<Node> nodes = processed.getNodes();

        assertValidNode(findNode(nodes, "type0_template"), "node_radial_stub");
        assertValidNode(findNode(nodes, "type1_template"), "type1_radial_stub_override");
        assertValidNode(findNode(nodes, "type2_template"), "type2_radial_stub");
        assertValidNode(findNode(nodes, "type3_template"), "type3_radial_stub");
        assertValidNode(findNode(nodes, "type1_sub_template"), "type1_radial_stub_override");
        assertValidNode(findNode(nodes, "type2_sub_template"), "type2_sub_radial_stub_override");
        assertValidNode(findNode(nodes, "type3_sub_template"), "type3_sub_template_radial_stub_override");

    }

    @Test(expectedExceptions = IllegalArgumentException.class,
          expectedExceptionsMessageRegExp = ".*service_template.*")
    public void testInvalidTwoServiceTemplates() {

        String invalidImportsDSLResource = "org/cloudifysource/cosmo/dsl/unit/imports/invalid/service_template/" +
                "dsl-with-imports-invalid-service-template.yaml";

        process(readResource(invalidImportsDSLResource));
    }

    @Test(expectedExceptions = IllegalArgumentException.class,
          expectedExceptionsMessageRegExp = ".*override definition.*")
    public void testInvalidOverrideDefinition() {

        String invalidImportsDSLResource = "org/cloudifysource/cosmo/dsl/unit/imports/invalid/definition/" +
                "dsl-with-imports-invalid-definition.yaml";

        process(readResource(invalidImportsDSLResource));
    }

    private void assertValidNode(Node node, String initWorkflow) {
        Assertions.assertThat(node.getWorkflows().get("init")).isEqualTo(initWorkflow);
    }

    private Node findNode(List<Node> nodes, String id) {
        for (Node node : nodes) {
            if (id.equals(node.getId())) {
                return node;
            }
        }
        Assert.fail("Failed finding node: " + id);
        return null;
    }

}
