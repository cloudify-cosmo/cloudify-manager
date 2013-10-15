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

import org.testng.annotations.Test;

import java.util.List;
import java.util.Map;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests the import mechanism of the {@link org.cloudifysource.cosmo.dsl.DSLProcessor}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessorPluginsTest extends AbstractDSLProcessorTest {

    @Test
    public void testValidOperations() {

        String validImportsDSLResource = "org/cloudifysource/cosmo/dsl/unit/plugins/fully_qualified/fully_qualified" +
                ".yaml";

        Processed processed = process(validImportsDSLResource);

        List<Node> nodes = processed.getNodes();

        Node node = findNode(nodes, "test_service_template.test_host");

        Map<String, String> operations = node.getOperations();

        assertThat(operations.get("some_op")).isEqualTo("test.plugin");
        assertThat(operations.get("test.interface.some_op")).isEqualTo("test.plugin");
        assertThat(operations.get("test.interface.provision")).isEqualTo("test.plugin");
        assertThat(operations.get("cloudify.tosca.interfaces.host_provisioner.provision")).isEqualTo(
                "cloudify.plugins.host_provisioner");
        assertThat(operations.get("provision")).isNull();

    }

}
