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

package org.cloudifysource.cosmo.bootstrap.ssh;

import com.google.common.base.Joiner;

import java.util.Map;

/**
 * Script files related utility methods.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class ScriptUtils {

    /**
     * @param env Map with variables to be expored.
     * @return a String in which every line matches an export statement matching an entry in 'env'
     */
    public static String toEnvScript(Map<String, String> env) {
        StringBuilder result = new StringBuilder("export ");
        return Joiner.on("\nexport ")
                .withKeyValueSeparator("=")
                .appendTo(result, env)
                .toString();
    }

}
