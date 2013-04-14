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

import com.beust.jcommander.internal.Maps;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.orchestrator.recipe.Appliance;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import java.util.HashSet;
import java.util.Map;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RuoteWorkflowExecutorTest {

    @BeforeMethod
    public void before() {
        RuoteJavaParticipant.reset();
    }

    @Test
    public void testWorkflowExecution() {
        WorkflowExecutor executor = new RuoteWorkflowExecutor();
        executor.execute("workflows/radial/java_workflow.radial");
        assertThat(RuoteJavaParticipant.get()).isEqualTo(3);
    }

    @Test
    public void testWorkflowPropertiesInjection() {

        Appliance appliance1 = new Appliance.Builder().name("vm_appliance1").build();
        Appliance appliance2 = new Appliance.Builder().name("vm_appliance2").build();
        Appliance appliance3 = new Appliance.Builder().name("vm_appliance3").build();

        final HashSet<Object> appliances = Sets.newHashSet();
        appliances.add(appliance1.toMap());
        appliances.add(appliance2.toMap());
        appliances.add(appliance3.toMap());

        final Map<String, Object> props = Maps.newHashMap();
        props.put("appliances", appliances);

        WorkflowExecutor executor = new RuoteWorkflowExecutor(props);
        executor.execute("workflows/radial/java_workflow_properties.radial");
        assertThat(RuoteJavaParticipant.get()).isEqualTo(3);
    }


}
