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

import com.google.common.collect.Lists;
import org.testng.annotations.Test;

import java.util.List;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessorRelationshipTemplateTest extends AbstractDSLProcessorTest {

    private static final String DSL_PATH = "org/cloudifysource/cosmo/dsl/unit/relationship_templates/" +
            "dsl-with-relationship-templates.yaml";

    @Test
    public void testRelationshipTemplate() {

        Processed processed = process(DSL_PATH);

        List<ProcessedRelationshipTemplate> relationshipTemplates1 = findNode(processed.getNodes(),
                "service_template.webserver1").getRelationships();

        List<ProcessedRelationshipTemplate> relationshipTemplates2 = findNode(processed.getNodes(),
                "service_template.webserver2").getRelationships();

        List<ProcessedRelationshipTemplate> relationshipTemplates3 = findNode(processed.getNodes(),
                "service_template.webserver3").getRelationships();

        assertThat(relationshipTemplates1.size()).isEqualTo(1);
        assertThat(relationshipTemplates2.size()).isEqualTo(1);
        assertThat(relationshipTemplates3.size()).isEqualTo(3);

        assertThat(relationshipTemplates1.get(0).getType()).isEqualTo("cloudify.tosca.relationships.hosted_on");
        assertThat(relationshipTemplates1.get(0).getTargetId()).isEqualTo("service_template.host1");
        assertThat(relationshipTemplates1.get(0).isLateBinding()).isFalse();
        assertThat(relationshipTemplates1.get(0).getExecutionOrder()).isEqualTo(
                Lists.newArrayList("source", "target"));

        assertThat(relationshipTemplates2.get(0).getType()).isEqualTo("cloudify.tosca.relationships.hosted_on");
        assertThat(relationshipTemplates2.get(0).getTargetId()).isEqualTo("service_template.host1");
        assertThat(relationshipTemplates2.get(0).isLateBinding()).isTrue();
        assertThat(relationshipTemplates2.get(0).getExecutionOrder()).isEqualTo(
                Lists.newArrayList("target", "source"));

        assertThat(relationshipTemplates3.get(0).getTargetId()).isEqualTo("service_template.host1");
        assertThat(relationshipTemplates3.get(1).getTargetId()).isEqualTo("service_template.host2");
        assertThat(relationshipTemplates3.get(2).getTargetId()).isEqualTo("service_template.host3");

    }


}
