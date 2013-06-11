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
import com.google.common.collect.Lists;
import com.google.common.io.Files;
import com.google.common.io.Resources;

import java.io.File;
import java.net.URI;
import java.net.URL;
import java.util.List;

/**
 * Load an import as a string.
 * Resolving order:
 * 1) Resolve as resource
 * 2) Resolve as file
 * 3) Resolve as URI
 * 4) Fail.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class ImportsLoader {

    /**
     * Load an import as a string.
     * Resolving order:
     * 1) Resolve as resource
     * 2) Resolve as file
     * 3) Resolve as URI
     * 4) Fail.
     *
     * @param anImport the import to load
     * @return The import as a string
     * @throws IllegalArgumentException if import not found
     */
    public static String load(String anImport) {
        List<Exception> suppressedException = Lists.newArrayList();

        // First try to load classpath resource
        try {
            URL resource = Resources.getResource(anImport);
            return Resources.toString(resource, Charsets.UTF_8);
        } catch (Exception e) {
            suppressedException.add(e);
        }

        // next, try to load from file.
        try {
            File file = new File(anImport);
            return Files.toString(file, Charsets.UTF_8);
        } catch (Exception e) {
            suppressedException.add(e);
        }

        // lastly, treat import as URI
        try {
            URL url = URI.create(anImport).toURL();
            return Resources.toString(url, Charsets.UTF_8);
        } catch (Exception e) {
            suppressedException.add(e);
        }

        // Not sure what to do about the suppressed exceptions yet (if ever)
        throw new IllegalArgumentException("Could not load import from [" + anImport + "]");

    }

}
