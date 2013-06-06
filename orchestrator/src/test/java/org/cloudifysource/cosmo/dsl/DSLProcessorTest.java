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

import com.google.common.base.Charsets;
import com.google.common.base.Throwables;
import com.google.common.io.Resources;
import org.testng.annotations.Test;

import java.io.IOException;
import java.net.URL;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessorTest {

    @Test
    public void testDsl() throws IOException {
        process("org/cloudifysource/cosmo/dsl/dsl.json");
    }

//    @Test
    public void testTypeHierarcy() {
        process("org/cloudifysource/cosmo/dsl/unit/type-hierarchy.json");
    }

    private static void process(String resourceName) {
        try {
            URL url = Resources.getResource(resourceName);
            String jsonDsl = Resources.toString(url, Charsets.UTF_8);
            DSLProcessor.process(jsonDsl);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

}
