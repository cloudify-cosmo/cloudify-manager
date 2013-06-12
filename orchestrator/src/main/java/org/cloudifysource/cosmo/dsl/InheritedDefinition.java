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

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Objects;
import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

import java.util.List;
import java.util.Map;

/**
 * A base class used to represent all definitions of the dsl that can be inherited.
 * Used internally only by the dsl processor.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public abstract class InheritedDefinition extends Definition {

    private List<String> superTypes = Lists.newArrayList();
    private String derivedFrom;
    private Map<String, Object> properties = Maps.newHashMap();

    public String getDerivedFrom() {
        return derivedFrom;
    }

    public void setDerivedFrom(String derivedFrom) {
        this.derivedFrom = derivedFrom;
    }

    public Map<String, Object> getProperties() {
        return properties;
    }

    public void setProperties(Map<String, Object> properties) {
        this.properties = properties;
    }

    @JsonIgnore
    public List<String> getSuperTypes() {
        return superTypes;
    }

    @JsonIgnore
    public void setSuperTypes(List<String> superTypes) {
        this.superTypes = superTypes;
    }

    protected void inheritPropertiesFrom(InheritedDefinition other) {
        getProperties().putAll(other.getProperties());
    }

    @JsonIgnore
    protected void setSuperTypes(InheritedDefinition parentDefinition) {
        List<String> newSuperTypes = Lists.newArrayList(parentDefinition.getName());
        if (parentDefinition.getSuperTypes() != null) {
            newSuperTypes.addAll(parentDefinition.getSuperTypes());
        }
        this.superTypes = newSuperTypes;
    }

    @JsonIgnore
    public boolean isInstanceOf(String otherType) {
        Preconditions.checkState(superTypes != null, "Cannot call this method before super types have been set");
        if (Objects.equal(otherType, getName())) {
            return true;
        }
        for (String superType : superTypes) {
            if (Objects.equal(otherType, superType)) {
                return true;
            }
        }
        return false;
    }
}
