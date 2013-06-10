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

import com.google.common.base.Optional;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;

import java.util.List;
import java.util.Map;

/**
 * A class used to represent a type.
 * Used internally only by the dsl processor.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Type extends InheritedDefinition {

    public static final String ROOT_NODE_TYPE_NAME = "node";
    public static final Type ROOT_NODE_TYPE = initRootNodeType();

    private static Type initRootNodeType() {
        Type root = new Type();
        root.setName(ROOT_NODE_TYPE_NAME);
        return root;
    }

    private List<Object> interfaces = Lists.newArrayList();

    public List<Object> getInterfaces() {
        return interfaces;
    }

    public void setInterfaces(List<Object> interfaces) {
        this.interfaces = interfaces;
    }

    public Type newInstanceWithInheritance(Type parent) {
        Type result = new Type();
        result.inheritPropertiesFrom(parent);
        result.inheritPropertiesFrom(this);
        result.setName(getName());
        result.setSuperTypes(parent);
        return result;
    }

    protected void inheritPropertiesFrom(Type other) {
        super.inheritPropertiesFrom(other);

        List<InterfaceDescription> interfacesDescriptions = Lists.newArrayList();
        for (Object rawInterface : interfaces) {
            interfacesDescriptions.add(InterfaceDescription.from(rawInterface));
        }

        for (Object rawOtherInterface : other.getInterfaces()) {
            InterfaceDescription otherInterface = InterfaceDescription.from(rawOtherInterface);

            for (InterfaceDescription interfaceDescription : interfacesDescriptions) {
                if (otherInterface.name.equals(interfaceDescription.name)) {
                    interfaceDescription.implementation = otherInterface.implementation;
                }
            }

        }

        List<Object> newInterfaces = Lists.newArrayList();
        for (InterfaceDescription interfaceDescription : interfacesDescriptions) {
            newInterfaces.add(interfaceDescription.toInterfaceRep());
        }
        setInterfaces(newInterfaces);
    }

    /**
     */
    static class InterfaceDescription {
        private String name;
        private String implementation;
        public InterfaceDescription(String name, String implementation) {
            this.name = name;
            this.implementation = implementation;
        }

        static InterfaceDescription from(Object obj) {
            try {
                if (obj instanceof String) {
                    return new InterfaceDescription((String) obj, null);
                } else if (obj instanceof Map) {
                    Map<String, String> tuple = (Map<String, String>) obj;
                    Map.Entry<String, String> entry = tuple.entrySet().iterator().next();
                    return new InterfaceDescription(entry.getKey(), entry.getValue());
                } else {
                    throw new IllegalArgumentException("Invalid interface element");
                }
            } catch (Exception e) {
                throw Throwables.propagate(e);
            }
        }

        Map<String, String> toInterfaceRep() {
            return ImmutableMap.<String, String>builder()
                    .put(name, implementation != null ? implementation : "")
                    .build();
        }

        public String getName() {
            return name;
        }

        public Optional<String> getImplementation() {
            return Optional.fromNullable(implementation);
        }

    }

}
