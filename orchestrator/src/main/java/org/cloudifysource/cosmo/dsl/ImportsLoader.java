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
     * The import will be first treated as is and on failure a 2nd attempt using a resolved location based on the
     * current context URI or base URI will take place.
     *
     * @param anImport the import to load
     * @param context
     * @return The import as a string
     * @throws IllegalArgumentException if import not found
     */
    public static DSLImport load(String anImport, ImportContext context) {

        List<Exception> suppressedException = Lists.newArrayList();

        // Try to locate the import as is and if not found resolve to a URI according to current context and try again
        String[] imports = new String[] {anImport, resolveDslUri(anImport, context).toString()};

        for (String importLocation : imports) {
            DSLImport dslImport = null;

            // First try to load classpath resource
            try {
                URL resource = Resources.getResource(importLocation);
                dslImport = new DSLImport(Resources.toString(resource, Charsets.UTF_8), resource.toURI());
            } catch (Exception e) {
                suppressedException.add(e);
            }

            // next, try to load from file.
            try {
                File file = new File(importLocation);
                dslImport = new DSLImport(Files.toString(file, Charsets.UTF_8), URI.create(importLocation));
            } catch (Exception e) {
                suppressedException.add(e);
            }

            // lastly, treat import as URI
            try {
                final URI uri = URI.create(importLocation);
                dslImport = new DSLImport(Resources.toString(uri.toURL(), Charsets.UTF_8), uri);
            } catch (Exception e) {
                suppressedException.add(e);
            }

            if (dslImport != null) {
                return dslImport;
            }
        }

        // Not sure what to do about the suppressed exceptions yet (if ever)
        throw new IllegalArgumentException("Could not load import from [" + anImport + "]");

    }

    private static URI resolveDslUri(String anImport, ImportContext context) {
        if (anImport.startsWith("/")) {
            return URI.create(context.getBaseUri().toString() + anImport.substring(1));
        }
        return URI.create(context.getContextUri().toString() + anImport);
    }


}
