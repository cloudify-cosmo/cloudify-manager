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
        assertThat(node1.getPolicies()).isEqualTo("host policy stub..");
        Node node2 = findNode(processed.getNodes(), "web_server.webserver_middleware");
        assertThat(node2.getPolicies()).isEmpty();
    }

}
