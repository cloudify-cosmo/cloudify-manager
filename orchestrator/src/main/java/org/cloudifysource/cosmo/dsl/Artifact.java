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
 * A class used to represent an artifact of the dsl.
 * Used internally only by the dsl processor.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Artifact extends InheritedDefinition {

    public static final String ROOT_ARTIFACT_NAME = "artifact";
    public static final Artifact ROOT_ARTIFACT = initRootArtifact();

    private static Artifact initRootArtifact() {
        Artifact root = new Artifact();
        root.setName(ROOT_ARTIFACT_NAME);
        return root;
    }

    public Artifact newInstanceWithInheritance(Artifact parent) {
        Artifact result = new Artifact();
        result.inheritPropertiesFrom(parent);
        result.inheritPropertiesFrom(this);
        result.setName(getName());
        result.setSuperTypes(parent);
        return result;
    }

    protected void inheritPropertiesFrom(Artifact other) {
        super.inheritPropertiesFrom(other);
    }
}
