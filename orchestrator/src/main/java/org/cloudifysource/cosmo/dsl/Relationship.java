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

/**
 * A class used to represent a relationship.
 * Used internally only by the dsl processor.
*
* @author Dan Kilman
* @since 0.1
*/
public class Relationship extends InheritedDefinition {

    public static final String ROOT_RELATIONSHIP_NAME = "relationship";
    public static final Relationship ROOT_RELATIONSHIP = initRootRelationship();

    private Interface anInterface;
    private String workflow;

    private static Relationship initRootRelationship() {
        Relationship root = new Relationship();
        root.setName(ROOT_RELATIONSHIP_NAME);
        return root;
    }

    public Relationship() {
        // Default value
        setDerivedFrom(ROOT_RELATIONSHIP_NAME);
    }

    @Override
    public InheritedDefinition newInstanceWithInheritance(InheritedDefinition parent) {
        Relationship typedParent = (Relationship) parent;
        Relationship result = new Relationship();
        result.inheritPropertiesFrom(typedParent);
        result.inheritPropertiesFrom(this);
        result.setName(getName());
        result.setSuperTypes(parent);
        return result;
    }

    protected void inheritPropertiesFrom(Relationship other) {
        super.inheritPropertiesFrom(other);
        if (other.getWorkflow() != null) {
            setWorkflow(other.getWorkflow());
        }
        if (other.getInterface() != null) {
            setInterface(other.getInterface());
        }
    }

    public String getWorkflow() {
        return workflow;
    }

    public void setWorkflow(String workflow) {
        this.workflow = workflow;
    }

    public Interface getInterface() {
        return anInterface;
    }

    public void setInterface(Interface anInterface) {
        this.anInterface = anInterface;
    }
}
