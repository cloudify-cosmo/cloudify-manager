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
public class Plugin extends InheritedDefinition {

    public static final String ROOT_PLUGIN_NAME = "plugin";
    public static final Plugin ROOT_PLUGIN = initRootPlugin();

    private static Plugin initRootPlugin() {
        Plugin root = new Plugin();
        root.setName(ROOT_PLUGIN_NAME);
        return root;
    }

    public Plugin() {
        // Default value
        setDerivedFrom(ROOT_PLUGIN_NAME);
    }

    @Override
    public InheritedDefinition newInstanceWithInheritance(InheritedDefinition parent) {
        Plugin typedParent = (Plugin) parent;
        Plugin result = new Plugin();
        result.inheritPropertiesFrom(typedParent);
        result.inheritPropertiesFrom(this);
        result.setName(getName());
        result.setSuperTypes(parent);
        return result;
    }

    protected void inheritPropertiesFrom(Plugin other) {
        super.inheritPropertiesFrom(other);
    }
}
