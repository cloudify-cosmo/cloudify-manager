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

import com.google.common.collect.Maps;
import org.testng.annotations.Test;

import java.util.Map;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Verifies plans in DSL are relevant for either a node type or node template.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLProcessorPlansTest extends AbstractDSLProcessorTest {

    @Test
    public void testValidPlans() {
        String dslPath = "org/cloudifysource/cosmo/dsl/unit/plans/dsl-with-valid-plans.yaml";
        Processed processed = process(dslPath);
        Map<String, Node> nodes = Maps.newHashMap();
        for (Node node : processed.getNodes()) {
            nodes.put(node.getId(), node);
        }
        assertInitPlan(nodes, "service_template.default_host", "plan1");
        assertInitPlan(nodes, "service_template.overridden_host", "plan2");
        assertInitPlan(nodes, "service_template.default_middleware", "plan3");
        assertInitPlan(nodes, "service_template.custom_template", "plan4");
    }

    private void assertInitPlan(Map<String, Node> nodes, String nodeId, String plan) {
        assertThat(nodes).containsKey(nodeId);
        final Node node = nodes.get(nodeId);
        final Object init = node.getWorkflows().get("init").toString();
        assertThat(init).isEqualTo(plan);
    }

}
