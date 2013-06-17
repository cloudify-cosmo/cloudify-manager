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
 * Tests multiple service templates logic of the {@link DSLProcessor}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessorGlobalPlanTest extends AbstractDSLProcessorTest {

    @Test
    public void testGlobalPlan() {
        String dslResource =
                "org/cloudifysource/cosmo/dsl/unit/global_plan/dsl-with-global-plan.yaml";
        Processed processed = process(readResource(dslResource));

        String globalWorkflow = processed.getGlobalWorkflow();
        assertThat(globalWorkflow).isEqualTo("definition_stub");
    }

    @Test(expectedExceptions = IllegalArgumentException.class,
          expectedExceptionsMessageRegExp = ".*Cannot override.*")
    public void testInvalidTwoGlobalWorkflows() {
        String dslResource =
                "org/cloudifysource/cosmo/dsl/unit/global_plan/dsl-with-global-plan-invalid-double-import.yaml";
        process(readResource(dslResource));
    }

}
