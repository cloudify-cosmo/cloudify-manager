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
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;

import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Post processor the prepares the map for the workflow consumption.
 * Auto wires interfaces to plugins.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class PluginArtifactAwareDSLPostProcessor implements DSLPostProcessor {

    public static final PluginArtifactAwareDSLPostProcessor INSTANCE =
            new PluginArtifactAwareDSLPostProcessor();

    @Override
    public Map<String, Object> postProcess(Definitions definitions,
                                           Map<String, TypeTemplate> populatedTypeTemplates,
                                           Map<String, Artifact> populatedArtifacts) {

        Map<String, Set<String>> interfacePluginImplementations =
                extractInterfacePluginImplementations(populatedArtifacts);

        Map<String, Object> result = Maps.newHashMap();
        List<Object> nodes = Lists.newArrayList();

        for (TypeTemplate typeTemplate : populatedTypeTemplates.values()) {
            nodes.add(processTypeTemplate(
                    typeTemplate,
                    definitions,
                    interfacePluginImplementations));
        }

        result.put("nodes", nodes);
        return result;
    }

    private Map<String, Set<String>> extractInterfacePluginImplementations(Map<String, Artifact> populatedArtifacts) {
        Map<String, Set<String>> interfacePluginImplementations = Maps.newHashMap();
        for (Artifact artifact : populatedArtifacts.values()) {
            if (!artifact.isInstanceOf("plugin")) {
                continue;
            }
            if (!artifact.getProperties().containsKey("interface") ||
                !(artifact.getProperties().get("interface") instanceof String)) {
                continue;
            }
            String pluginInterface = (String) artifact.getProperties().get("interface");
            Set<String> implementingPlugins = interfacePluginImplementations.get(pluginInterface);
            if (implementingPlugins == null) {
                implementingPlugins = Sets.newHashSet();
            }
            implementingPlugins.add(artifact.getName());
        }
        return interfacePluginImplementations;
    }

    private Map<String, Object> processTypeTemplate(TypeTemplate typeTemplate,
                                                    Definitions definitions,
                                                    Map<String, Set<String>> interfacesToPluginImplementations) {
        Map<String, Object> node = Maps.newHashMap();

        setNodeId(typeTemplate, node);

        setNodeProperties(typeTemplate, node);

        setNodeRelationships(typeTemplate, node);

        setNodeWorkflows(typeTemplate, definitions, node);

        setNodeOperations(typeTemplate, definitions, interfacesToPluginImplementations, node);

        return node;
    }

    private void setNodeId(TypeTemplate typeTemplate, Map<String, Object> node) {
        node.put("id", typeTemplate.getName());
    }

    private void setNodeProperties(TypeTemplate typeTemplate, Map<String, Object> node) {
        node.put("properties", typeTemplate.getProperties());
    }

    private void setNodeRelationships(TypeTemplate typeTemplate, Map<String, Object> node) {
        List<Object> relationships = Lists.newLinkedList();
        // TODO DSL Handle proper typing for relationship (i.e. should be in sync with relationship
        // inheritance
        for (Map.Entry<String, Object> entry : typeTemplate.getRelationships().entrySet()) {
            Map<String, Object> relationshipMap = Maps.newHashMap();
            relationshipMap.put("type", entry.getKey());
            relationshipMap.put("target_id", entry.getValue());
            relationships.add(relationshipMap);
        }
        node.put("relationships", relationships);
    }

    private void setNodeWorkflows(TypeTemplate typeTemplate, Definitions definitions, Map<String, Object> node) {
        Map<String, Object> workflows = Maps.newHashMap();

        // for now only inline radial is supported
        // later we'll add support for others

        // extract init
        Optional<Object> initWorkflow = extractWorkflow(definitions.getPlans(), typeTemplate.getName());
        Iterator<String> superTypes = typeTemplate.getSuperTypes().iterator();
        while (superTypes.hasNext() && !initWorkflow.isPresent()) {
            initWorkflow = extractWorkflow(definitions.getPlans(), superTypes.next());
        }
        if (!initWorkflow.isPresent()) {
            throw new IllegalArgumentException("No init workflow found for template: " + typeTemplate.getName());
        }
        workflows.put("init", initWorkflow);

        node.put("workflows", workflows);
    }

    private Optional<Object> extractWorkflow(Map<String, Plan> plans, String typeName) {
        Plan plan = plans.get(typeName);
        if (plan == null) {
            return Optional.absent();
        }
        Object initWorkflow = plan.getInit().get("radial");
        return Optional.fromNullable(initWorkflow);
    }

    private void setNodeOperations(TypeTemplate typeTemplate, Definitions definitions,
                                   Map<String, Set<String>> interfacesToPluginImplementations,
                                   Map<String, Object> node) {
        Set<String> sameNameOperations = Sets.newHashSet();
        Map<String, String> operationToPlugin = Maps.newHashMap();
        for (Object interfaceReference : typeTemplate.getInterfaces()) {

            Type.InterfaceDescription interfaceDescription = Type.InterfaceDescription.from(interfaceReference);

            // validate interface is define
            if (!definitions.getInterfaces().containsKey(interfaceDescription.getName())) {
                throw new IllegalArgumentException("Referencing non defined interface [" +
                        interfaceDescription.getName() + "]");
            }
            Interface theInterface = definitions.getInterfaces().get(interfaceDescription.getName());

            // find and validate exactly 1 matching plugin implementation
            Set<String> pluginImplementations = interfacesToPluginImplementations.get(interfaceDescription.getName());
            String pluginImplementation;
            if (interfaceDescription.getImplementation().isPresent()) {
                if (!pluginImplementations.contains(interfaceDescription.getImplementation().get())) {
                    throw new IllegalArgumentException("Explicit plugin [" + interfaceDescription.getImplementation()
                            .get());
                }
                pluginImplementation = interfaceDescription.getImplementation().get();
            } else {
                if (pluginImplementations.size() == 0) {
                    throw new IllegalArgumentException("No implementing plugin found for interface [" +
                            interfaceDescription.getName() + "]");
                }
                if (pluginImplementations.size() > 1) {
                    throw new IllegalArgumentException("More than 1 implementing plugin found for interface [" +
                            interfaceDescription.getName() + "]");
                }
                pluginImplementation = pluginImplementations.iterator().next();
            }

            Set<String> operations = Sets.newHashSet(theInterface.getOperations());
            for (String operation : operations) {
                // always add fully qualified name to operation
                operationToPlugin.put(pluginImplementation + "." + operation, pluginImplementation);

                // now try adding operation name on its own to simplify usage in workflow.
                // if we already find one, remove it so there will be no ambiguities
                // if we already found a duplicate, ignore.
                if (sameNameOperations.contains(operation)) {
                    continue;
                }

                if (operationToPlugin.containsKey(operation)) {
                    operationToPlugin.remove(operation);
                    sameNameOperations.add(operation);
                } else {
                    operationToPlugin.put(operation, pluginImplementation);
                }
            }
        }
        node.put("operations", operationToPlugin);
    }
}
