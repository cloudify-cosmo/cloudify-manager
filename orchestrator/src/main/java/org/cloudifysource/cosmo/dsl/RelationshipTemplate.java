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

import com.google.common.base.Strings;

/**
 * Data container for a relationship template in a node template of the dsl.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class RelationshipTemplate extends Relationship {

    private String target;

    public String getType() {
        return getDerivedFrom();
    }

    public void setType(String type) {
        setDerivedFrom(type);
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    @Override
    public InheritedDefinition newInstanceWithInheritance(InheritedDefinition parent) {
        Relationship typedParent = (Relationship) parent;
        RelationshipTemplate result = new RelationshipTemplate();
        result.inheritPropertiesFrom(typedParent);
        result.inheritPropertiesFrom(this);
        result.setName(getName());
        result.setDerivedFrom(parent.getName());
        result.setSuperTypes(parent);
        return result;
    }

    protected void inheritPropertiesFrom(RelationshipTemplate other) {
        super.inheritPropertiesFrom(other);
        if (!Strings.isNullOrEmpty(other.getTarget())) {
            setTarget(other.getTarget());
        }
    }

}
