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

import java.io.File;

/**
 * Helper methods for handling string based resource locations.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class ResourceLocationHelper {

    private static final String CLASSPATH_SEPARATOR = "/";

    /**
     * Gets the parent location substring of the provided resource location.
     * @param resourceLocation The resource location
     * @return The resource's parent location.
     */
    public static String getParentLocation(String resourceLocation) {
        String separator = getSeparator(resourceLocation);
        String location = resourceLocation;
        if (location.endsWith(separator)) {
            location = resourceLocation.substring(0, resourceLocation.length() - 1);
        }
        int index = location.lastIndexOf(separator);
        return index == -1 ? "" : location.substring(0, index);
    }

    /**
     * Concatenates the two resource location strings to a valid resource location string.
     *
     * @param resourceLocation The resource location.
     * @param subLocation The resource location to concatenate.
     * @return Concatenated resource location.
     */
    public static String createLocationString(String resourceLocation, String subLocation) {
        String separator = getSeparator(resourceLocation);
        String location;
        if (resourceLocation.endsWith(separator)) {
            location = String.format("%s%s",
                    resourceLocation,
                    subLocation.startsWith(separator) ? subLocation.substring(1) : subLocation);
        } else {
            location = String.format("%s%s%s",
                    resourceLocation,
                    separator,
                    subLocation.startsWith(separator) ? subLocation.substring(1) : subLocation);
        }
        return location.endsWith(separator) ? location.substring(0, location.length() - 1) : location;
    }

    private static String getSeparator(String resourceLocation) {
        if (resourceLocation.contains(File.separator)) {
            return File.separator;
        } else if (resourceLocation.contains(CLASSPATH_SEPARATOR)) {
            return CLASSPATH_SEPARATOR;
        }
        return File.separator;
    }

}
