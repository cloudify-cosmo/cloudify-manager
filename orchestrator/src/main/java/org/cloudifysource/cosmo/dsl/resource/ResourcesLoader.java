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

package org.cloudifysource.cosmo.dsl.resource;

import com.google.common.base.Charsets;
import com.google.common.collect.Lists;
import com.google.common.io.Files;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.dsl.ResourceLocationHelper;

import java.io.File;
import java.net.URI;
import java.net.URL;
import java.util.List;

/**
 * Load an resource as a string.
 * Resolving order:
 * 1) Resolve as classpath resource
 * 2) Resolve as file
 * 3) Resolve as URI
 * 4) Fail.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class ResourcesLoader {

    /**
     * Load an resource as a string.
     * Resolving order:
     * 1) Resolve as classpath resource
     * 2) Resolve as file
     * 3) Resolve as URI
     * 4) Fail.
     *
     * The resource will be first treated as is and on failure a 2nd attempt using a resolved location based on the
     * current context URI or base URI will take place.
     *
     * @param resource the resource to load
     * @param context
     * @return The resource as a string
     * @throws IllegalArgumentException if resource not found
     */
    public static DSLResource load(String resource, ResourceLoadingContext context) {

        List<Exception> suppressedException = Lists.newArrayList();

        resource = context.getMapping(resource);

        // Try to locate the import as is and if not found resolve to a URI according to current context and try again
        String[] resources = new String[] {resource, resolveDslLocation(resource, context)};

        for (String resourceLocation : resources) {
            DSLResource dslResource = null;

            // First try to load classpath resource
            try {
                URL classPathResource = Resources.getResource(resourceLocation);
                dslResource = new DSLResource(Resources.toString(classPathResource, Charsets.UTF_8),
                        classPathResource.getFile());
            } catch (Exception e) {
                suppressedException.add(e);
            }

            // next, try to load from file.
            try {
                File file = new File(resourceLocation);
                dslResource = new DSLResource(Files.toString(file, Charsets.UTF_8), resourceLocation);
            } catch (Exception e) {
                suppressedException.add(e);
            }

            // lastly, treat resource as URI
            try {
                dslResource = new DSLResource(
                        Resources.toString(URI.create(resourceLocation).toURL(), Charsets.UTF_8), resourceLocation);
            } catch (Exception e) {
                suppressedException.add(e);
            }

            if (dslResource != null) {
                return dslResource;
            }
        }

        // Not sure what to do about the suppressed exceptions yet (if ever)
        throw new IllegalArgumentException("Could not load resource from [" + resource + "]");

    }

    private static String resolveDslLocation(String anImport, ResourceLoadingContext context) {
        if (anImport.startsWith("/")) {
            return ResourceLocationHelper.createLocationString(context.getBaseLocation(), anImport);
        }
        return ResourceLocationHelper.createLocationString(context.getContextLocation(), anImport);
    }


}
