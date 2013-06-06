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

import com.google.common.collect.Maps;

import java.util.Map;

/**
 * A class used to represent a type template.
*
* @author Dan Kilman
* @since 0.1
*/
public class TypeTemplate extends Type {

    private Map<String, Object> relationships = Maps.newHashMap();

    public Map<String, Object> getRelationships() {
        return relationships;
    }

    public void setRelationships(Map<String, Object> relationships) {
        this.relationships = relationships;
    }

    public void inheritPropertiesFrom(TypeTemplate other) {
        super.inheritPropertiesFrom(other);
        relationships.putAll(other.getRelationships());
    }
}
