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

package org.cloudifysource.cosmo.manager;

import com.google.common.io.Resources;
import org.testng.Assert;
import org.testng.annotations.Test;

import java.io.IOException;

/**
 * Tests the {@link Validator} functionality.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public class ValidatorTest {

    @Test
    public void testOkDsl() throws IOException {
        String dslFile = "org/cloudifysource/cosmo/dsl/unit/validation/dsl-with-base-imports.yaml";
        Validator.validateDSL(dslFile);
    }

    @Test
    public void testInvalidDsl() throws IOException {
        String dslFile = "org/cloudifysource/cosmo/dsl/unit/validation/invalid-dsl.yaml";
        //Check the dsl file exists so the test will fail on legit reason and not bacause this file was moved
        Resources.getResource(dslFile);
        try {
            Validator.validateDSL(dslFile);
            Assert.fail();
        } catch (Exception e) {
            //We are expecting an exception since this is a dsl with error.
        }
    }

    @Test
    public void testInvalidDslNodeWithAgentPluginNoHostRelationship() throws IOException {
        String dslFile = "org/cloudifysource/cosmo/dsl/unit/validation/dsl-node-agent-plugin-no-host.yaml";
        //Check the dsl file exists so the test will fail on legit reason and not because this file was moved
        Resources.getResource(dslFile);
        try {
            Validator.validateDSL(dslFile);
            Assert.fail();
        } catch (Exception e) {
            Assert.assertTrue(e.getMessage().contains("relationship"));
            Assert.assertTrue(e.getMessage().contains("host"));
        }
    }
}
