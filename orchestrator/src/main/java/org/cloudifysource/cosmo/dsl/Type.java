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
import com.google.common.base.Strings;
import com.google.common.base.Throwables;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

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

    private List<Object> interfaces = Lists.newArrayList();
    private List<Policy> policies = Lists.newArrayList();
    private Map<String, Workflow> workflows = Maps.newHashMap();

    private static Type initRootNodeType() {
        Type root = new Type();
        root.setName(ROOT_NODE_TYPE_NAME);
        return root;
    }

    public Type() {
        // Default value
        setDerivedFrom(ROOT_NODE_TYPE_NAME);
    }

    public List<Object> getInterfaces() {
        return interfaces;
    }

    public void setInterfaces(List<Object> interfaces) {
        this.interfaces = interfaces;
    }

    public List<Policy> getPolicies() {
        return policies;
    }

    public void setPolicies(List<Policy> policies) {
        this.policies = policies;
    }

    public Map<String, Workflow> getWorkflows() {
        return workflows;
    }

    public void setWorkflows(Map<String, Workflow> workflows) {
        this.workflows = workflows;
    }

    @Override
    public InheritedDefinition newInstanceWithInheritance(InheritedDefinition parent) {
        Type typedParent = (Type) parent;
        Type result = new Type();
        result.inheritPropertiesFrom(typedParent);
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

            Optional<InterfaceDescription> interfaceDescription = findInterface(interfacesDescriptions, otherInterface);

            if (interfaceDescription.isPresent()) {
                interfaceDescription.get().setImplementation(otherInterface.implementation);
            } else {
                interfacesDescriptions.add(otherInterface);
            }

        }

        List<Object> newInterfaces = Lists.newArrayList();
        for (InterfaceDescription interfaceDescription : interfacesDescriptions) {
            newInterfaces.add(interfaceDescription.toInterfaceRep());
        }
        setInterfaces(newInterfaces);

        Map<String, Policy> newPoliciesMap = Maps.newLinkedHashMap();
        for (Policy policy : getPolicies()) {
            newPoliciesMap.put(policy.getName(), policy);
        }
        for (Policy policy : other.getPolicies()) {
            newPoliciesMap.put(policy.getName(), policy);
        }
        setPolicies(Lists.newArrayList(newPoliciesMap.values()));

        workflows.putAll(other.getWorkflows());
    }

    private Optional<InterfaceDescription> findInterface(List<InterfaceDescription> interfacesDescriptions,
                                                         InterfaceDescription otherInterface) {
        for (InterfaceDescription interfaceDescription : interfacesDescriptions) {
            if (otherInterface.name.equals(interfaceDescription.name)) {
                return Optional.of(interfaceDescription);
            }
        }
        return Optional.absent();
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
            return Strings.isNullOrEmpty(implementation) ? Optional.<String>absent() : Optional.of(implementation);
        }

        private void setImplementation(String implementation) {
            this.implementation = implementation;
        }

    }

}
