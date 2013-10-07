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

    private static final String DSL_PATH = "org/cloudifysource/cosmo/dsl/unit/policies/dsl-with-policies.yaml";

    @Test
    public void testPoliciesEventsDefinition() {
        Processed processed = process(DSL_PATH);
        assertThat(processed.getPoliciesEvents()).isNotNull().isNotEmpty();
        PolicyDefinition policyEvent = processed.getPoliciesEvents().get("start_detection_policy");
        assertThat(policyEvent.getMessage()).isEqualTo("start detection passed");
        assertThat(policyEvent).isNotNull();
        assertThat(policyEvent.getPolicy()).isNotEmpty();
    }

    @Test
    public void testPolicies() {
        Processed processed = process(DSL_PATH);
        Node node1 = findNode(processed.getNodes(), "web_server.webserver_host");
        assertThat(node1.getPolicies()).hasSize(2);
        Policy policy1 = node1.getPolicies().get("start_detection_policy");
        assertThat(policy1).isNotNull();
        assertThat(policy1.getRules()).hasSize(2);
        Rule rule1 = policy1.getRules().get(0);
        assertThat(rule1).isNotNull();
        assertThat(rule1.getType()).isEqualTo("state_equals");
        assertThat(rule1.getProperties()).hasSize(2);
        assertThat(rule1.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule1.getProperties().get("value")).isEqualTo("running");
        Rule rule2 = policy1.getRules().get(1);
        assertThat(rule2).isNotNull();
        assertThat(rule2.getType()).isEqualTo("metric_below");
        assertThat(rule2.getProperties()).hasSize(2);
        assertThat(rule2.getProperties().get("metric")).isEqualTo("latency");
        assertThat(rule2.getProperties().get("value")).isEqualTo("100");
        Policy policy2 = node1.getPolicies().get("failure_detection_policy");
        assertThat(policy2).isNotNull();
        assertThat(policy2.getRules()).hasSize(1);
        Rule rule3 = policy2.getRules().get(0);
        assertThat(rule3).isNotNull();
        assertThat(rule3.getType()).isEqualTo("state_not_equals");
        assertThat(rule3.getProperties()).hasSize(2);
        assertThat(rule3.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule3.getProperties().get("value")).isEqualTo("running");
    }

    @Test
    public void testEmptyPolicies() {
        Processed processed = process(DSL_PATH);
        Node node2 = findNode(processed.getNodes(), "web_server.webserver_middleware");
        assertThat(node2.getPolicies()).isEmpty();
    }

    @Test
    public void testPoliciesInheritance() {
        Processed processed = process(DSL_PATH);
        Node node1 = findNode(processed.getNodes(), "web_server.template_with_inherited_policy");
        assertThat(node1.getPolicies()).hasSize(1);
        Policy policy1 = node1.getPolicies().get("start_detection_policy");
        assertThat(policy1).isNotNull();
        assertThat(policy1.getRules()).hasSize(1);
        Rule rule1 = policy1.getRules().get(0);
        assertThat(rule1).isNotNull();
        assertThat(rule1.getType()).isEqualTo("state_equals");
        assertThat(rule1.getProperties()).hasSize(2);
        assertThat(rule1.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule1.getProperties().get("value")).isEqualTo("running");
    }

    @Test
    public void testMergingOfPoliciesInheritance() {
        Processed processed = process(DSL_PATH);
        Node node1 = findNode(processed.getNodes(), "web_server.template_with_inherited_policy_and_additional_policy");
        assertThat(node1.getPolicies()).hasSize(2);
        Policy policy1 = node1.getPolicies().get("start_detection_policy");
        assertThat(policy1).isNotNull();
        assertThat(policy1.getRules()).hasSize(1);
        Rule rule1 = policy1.getRules().get(0);
        assertThat(rule1).isNotNull();
        assertThat(rule1.getType()).isEqualTo("state_equals");
        assertThat(rule1.getProperties()).hasSize(2);
        assertThat(rule1.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule1.getProperties().get("value")).isEqualTo("running");
        Policy policy2 = node1.getPolicies().get("failure_detection_policy");
        assertThat(policy2).isNotNull();
        assertThat(policy2.getRules()).hasSize(1);
        Rule rule3 = policy2.getRules().get(0);
        assertThat(rule3).isNotNull();
        assertThat(rule3.getType()).isEqualTo("state_equals");
        assertThat(rule3.getProperties()).hasSize(2);
        assertThat(rule3.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule3.getProperties().get("value")).isEqualTo("terminated");

        Node node2 = findNode(processed.getNodes(), "web_server.2nd_template_with_inherited_policy");
        assertThat(node2.getPolicies()).hasSize(2);
        Policy policy3 = node2.getPolicies().get("start_detection_policy");
        assertThat(policy3).isNotNull();
        assertThat(policy3.getRules()).hasSize(1);
        Rule rule4 = policy3.getRules().get(0);
        assertThat(rule4).isNotNull();
        assertThat(rule4.getType()).isEqualTo("state_not_equals");
        assertThat(rule4.getProperties()).hasSize(2);
        assertThat(rule4.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule4.getProperties().get("value")).isEqualTo("terminated");
        Policy policy4 = node2.getPolicies().get("failure_detection_policy");
        assertThat(policy4).isNotNull();
        assertThat(policy4.getRules()).hasSize(1);
        Rule rule5 = policy4.getRules().get(0);
        assertThat(rule5).isNotNull();
        assertThat(rule5.getType()).isEqualTo("state_equals");
        assertThat(rule5.getProperties()).hasSize(2);
        assertThat(rule5.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule5.getProperties().get("value")).isEqualTo("terminated");

        Node node3 = findNode(processed.getNodes(), "web_server.2nd_template_with_overridden_policy");
        assertThat(node3.getPolicies()).hasSize(2);
        Policy policy5 = node3.getPolicies().get("start_detection_policy");
        assertThat(policy5).isNotNull();
        assertThat(policy5.getRules()).hasSize(1);
        Rule rule6 = policy5.getRules().get(0);
        assertThat(rule6).isNotNull();
        assertThat(rule6.getType()).isEqualTo("state_not_equals");
        assertThat(rule6.getProperties()).hasSize(2);
        assertThat(rule6.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule6.getProperties().get("value")).isEqualTo("terminated");
        Policy policy6 = node3.getPolicies().get("failure_detection_policy");
        assertThat(policy6).isNotNull();
        assertThat(policy6.getRules()).hasSize(1);
        Rule rule7 = policy6.getRules().get(0);
        assertThat(rule7).isNotNull();
        assertThat(rule7.getType()).isEqualTo("state_equals");
        assertThat(rule7.getProperties()).hasSize(2);
        assertThat(rule7.getProperties().get("state")).isEqualTo("host_state");
        assertThat(rule7.getProperties().get("value")).isEqualTo("terminated");
    }


    @Test(expectedExceptions = IllegalArgumentException.class)
    public void testUnknownPolicyValidation() {
        process("org/cloudifysource/cosmo/dsl/unit/policies/dsl-with-unknown-policy.yaml");
    }

    @Test(expectedExceptions = IllegalArgumentException.class)
    public void testUnknownRuleValidation() {
        process("org/cloudifysource/cosmo/dsl/unit/policies/dsl-with-unknown-rule.yaml");
    }

}
