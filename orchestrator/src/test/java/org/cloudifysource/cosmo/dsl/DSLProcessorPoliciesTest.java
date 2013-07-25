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

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class DSLProcessorPoliciesTest extends AbstractDSLProcessorTest {

    @Test
    public void testPolicies() {
        String dslPath = "org/cloudifysource/cosmo/dsl/unit/policies/dsl-with-policies.yaml";
        Processed processed = process(dslPath);
        Node node1 = findNode(processed.getNodes(), "web_server.webserver_host");
        assertThat(node1.getPolicies()).hasSize(2);
        Policy policy1 = node1.getPolicies().get("start_detection");
        assertThat(policy1).isNotNull();
        assertThat(policy1.getRules()).hasSize(2);
        assertThat(policy1.getOnEvent()).hasSize(2);
        assertThat(policy1.getOnEvent().get("reachable")).isEqualTo("true");
        assertThat(policy1.getOnEvent().get("ip")).isEqualTo("10.0.0.1");
        Rule rule1 = policy1.getRules().get("host_status");
        assertThat(rule1).isNotNull();
        assertThat(rule1.getType()).isEqualTo("state_equals");
        assertThat(rule1.getProperties()).hasSize(2);
        assertThat(rule1.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule1.getProperties().get("value")).isEqualTo("running");
        Rule rule2 = policy1.getRules().get("ping_latency");
        assertThat(rule2).isNotNull();
        assertThat(rule2.getType()).isEqualTo("metric_below");
        assertThat(rule2.getProperties()).hasSize(2);
        assertThat(rule2.getProperties().get("metric")).isEqualTo("latency");
        assertThat(rule2.getProperties().get("value")).isEqualTo("100");
        Policy policy2 = node1.getPolicies().get("failure_detection");
        assertThat(policy2).isNotNull();
        assertThat(policy2.getRules()).hasSize(1);
        assertThat(policy2.getOnEvent()).hasSize(1);
        assertThat(policy2.getOnEvent().get("reachable")).isEqualTo("false");
        Rule rule3 = policy2.getRules().get("host_status");
        assertThat(rule3).isNotNull();
        assertThat(rule3.getType()).isEqualTo("state_not_equals");
        assertThat(rule3.getProperties()).hasSize(2);
        assertThat(rule3.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule3.getProperties().get("value")).isEqualTo("running");

        Node node2 = findNode(processed.getNodes(), "web_server.webserver_middleware");
        assertThat(node2.getPolicies()).isEmpty();
    }

}
