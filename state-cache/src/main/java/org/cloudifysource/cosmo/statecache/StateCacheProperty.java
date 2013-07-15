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

package org.cloudifysource.cosmo.statecache;

/**
 * A key for a value which is stored inside the {@link StateCache}.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public class StateCacheProperty {

    private final String resourceId;
    private final String property;

    public StateCacheProperty(String resourceId, String property) {
        this.resourceId = resourceId;
        this.property = property;
    }

    public String getResourceId() {
        return resourceId;
    }

    public String getProperty() {
        return property;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        StateCacheProperty that = (StateCacheProperty) o;

        if (property != null ? !property.equals(that.property) : that.property != null) return false;
        if (resourceId != null ? !resourceId.equals(that.resourceId) : that.resourceId != null) return false;

        return true;
    }

    @Override
    public int hashCode() {
        int result = resourceId != null ? resourceId.hashCode() : 0;
        result = 31 * result + (property != null ? property.hashCode() : 0);
        return result;
    }
}
