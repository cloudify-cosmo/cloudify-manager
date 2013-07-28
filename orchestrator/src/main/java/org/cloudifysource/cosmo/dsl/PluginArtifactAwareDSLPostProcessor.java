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

import com.google.common.base.Objects;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
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

    private static final String CLOUDIFY_TOSCA_ARTIFACTS_PLUGIN = "cloudify.tosca.artifacts.plugin";
    private static final String CLOUDIFY_TOSCA_ARTIFACTS_REMOTE_PLUGIN = "cloudify.tosca.artifacts.remote_plugin";
    private static final String CLOUDIFY_TOSCA_ARTIFACTS_WORKER_PLUGIN = "cloudify.tosca.artifacts.agent_plugin";

    @Override
    public Map<String, Object> postProcess(Definitions definitions,
                                           Map<String, ServiceTemplate> populatedServiceTemplates,
                                           Map<String, Artifact> populatedArtifacts) {

        Map<String, Set<String>> interfacePluginImplementations =
                extractInterfacePluginImplementations(definitions.getInterfaces(), populatedArtifacts);

        Map<String, Object> result = Maps.newHashMap();
        List<Object> nodes = Lists.newArrayList();
        Map<String, Object> nodesExtraData = Maps.newHashMap();
        Map<String, Map<String, Policy>> policies = Maps.newHashMap();

        for (ServiceTemplate serviceTemplate : populatedServiceTemplates.values()) {
            for (TypeTemplate typeTemplate : serviceTemplate.getTopology().values()) {
                // Type template name we be prepended with the service template
                String nodeId = serviceTemplate.getName() + "." + typeTemplate.getName();
                typeTemplate.setName(nodeId);
                Map<String, Object> node = processTypeTemplateNode(
                        serviceTemplate.getName(),
                        typeTemplate,
                        definitions,
                        interfacePluginImplementations,
                        populatedArtifacts);
                Map<String, Object> nodeExtraData = processTypeTemplateNodeExtraData(
                        serviceTemplate.getName(),
                        typeTemplate);
                nodes.add(node);
                nodesExtraData.put(nodeId, nodeExtraData);
                policies.put(nodeId, typeTemplate.getPolicies());
            }
        }

        result.put("nodes", nodes);
        result.put("nodes_extra", nodesExtraData);
        result.put("rules_content", definitions.getPolicies().getRules());
        result.put("policies", policies);
        return result;
    }

    private Map<String, Object> processTypeTemplateNodeExtraData(String serviceTemplateName,
                                                                 TypeTemplate typeTemplate) {
        Map<String, Object> nodeExtraData = Maps.newHashMap();

        setNodeSuperTypes(typeTemplate, nodeExtraData);

        setNodeFlattenedRelationships(typeTemplate, serviceTemplateName, nodeExtraData);

        return nodeExtraData;
    }


    private Map<String, Object> processTypeTemplateNode(String serviceTemplateName,
                                                        TypeTemplate typeTemplate,
                                                        Definitions definitions,
                                                        Map<String, Set<String>> interfacesToPluginImplementations,
                                                        Map<String, Artifact> populatedArtifacts) {
        Map<String, Object> node = Maps.newHashMap();

        setNodeId(typeTemplate, node);

        setNodeProperties(typeTemplate, node);

        setNodeRelationships(typeTemplate, serviceTemplateName, node);

        setNodeWorkflows(typeTemplate, definitions, node);

        setNodePolicies(typeTemplate, node);

        setNodeOperationsAndPlugins(typeTemplate,
                                    definitions,
                                    interfacesToPluginImplementations,
                                    node,
                                    populatedArtifacts);


        return node;
    }

    private Map<String, Set<String>> extractInterfacePluginImplementations(Map<String, Interface> interfaces,
                                                                           Map<String, Artifact> populatedArtifacts) {
        Map<String, Set<String>> interfacePluginImplementations = Maps.newHashMap();
        for (String interfaceName : interfaces.keySet()) {
            interfacePluginImplementations.put(interfaceName, Sets.<String>newHashSet());
        }

        for (Artifact artifact : populatedArtifacts.values()) {
            if (!artifact.isInstanceOf(CLOUDIFY_TOSCA_ARTIFACTS_PLUGIN) ||
                    Objects.equal(CLOUDIFY_TOSCA_ARTIFACTS_PLUGIN, artifact.getName())) {
                continue;
            }
            Preconditions.checkArgument(
                    artifact.isInstanceOf(
                            CLOUDIFY_TOSCA_ARTIFACTS_REMOTE_PLUGIN) ||
                            artifact.isInstanceOf(CLOUDIFY_TOSCA_ARTIFACTS_WORKER_PLUGIN),
                    "Plugin [%s] cannot be derived directly from [%s]", artifact.getName(),
                    CLOUDIFY_TOSCA_ARTIFACTS_PLUGIN);
            if (!artifact.getProperties().containsKey("interface") ||
                !(artifact.getProperties().get("interface") instanceof String)) {
                continue;
            }
            String pluginInterface = (String) artifact.getProperties().get("interface");
            Set<String> implementingPlugins = interfacePluginImplementations.get(pluginInterface);
            if (implementingPlugins == null) {
                throw new IllegalArgumentException("Plugin references a non defined interface [" +
                        pluginInterface + "]");
            }
            implementingPlugins.add(artifact.getName());
            interfacePluginImplementations.put(pluginInterface, implementingPlugins);
        }
        return interfacePluginImplementations;
    }

    private void setNodeId(TypeTemplate typeTemplate, Map<String, Object> node) {
        node.put("id", typeTemplate.getName());
    }

    private void setNodeProperties(TypeTemplate typeTemplate, Map<String, Object> node) {
        node.put("properties", typeTemplate.getProperties());
    }

    private void setNodeRelationships(TypeTemplate typeTemplate, String serviceTemplateName, Map<String, Object> node) {
        List<Object> relationships = Lists.newLinkedList();
        // TODO 1) DSL Handle proper typing for relationship (i.e. should be in sync with relationship
        // inheritance
        // 2) Also, currently relation is assumed to be in the same service
        // should be fixed
        // 3) the relationship value is currently always String denoting the name of the target
        // but this should be extended to allow more than one target and perhaps
        // a complex target with properties that refine the relationship
        for (Map.Entry<String, Object> entry : typeTemplate.getRelationships().entrySet()) {
            Map<String, Object> relationshipMap = Maps.newHashMap();
            relationshipMap.put("type", entry.getKey());
            String fullTargetId = extractFullTargetIdFromRelationship(serviceTemplateName, entry);
            relationshipMap.put("target_id", fullTargetId);
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
        workflows.put("init", initWorkflow.get());

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

    private void setNodePolicies(TypeTemplate typeTemplate, Map<String, Object> node) {
        final Map<String, Policy> policies =
                typeTemplate.getPolicies() != null ? typeTemplate.getPolicies() : Maps.<String, Policy>newHashMap();
        node.put("policies", policies);
    }

    private void setNodeOperationsAndPlugins(TypeTemplate typeTemplate, Definitions definitions,
                                             Map<String, Set<String>> interfacesToPluginImplementations,
                                             Map<String, Object> node, Map<String, Artifact> populatedArtifacts) {
        Set<String> sameNameOperations = Sets.newHashSet();
        Map<String, String> operationToPlugin = Maps.newHashMap();
        Map<String, Map<String, Object>> plugins = Maps.newHashMap();
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
                            .get() + "] not defined.");
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

            Map<String, Object> pluginDetails = Maps.newHashMap();
            Artifact plugin = populatedArtifacts.get(pluginImplementation);
            boolean agentPlugin = plugin.isInstanceOf(CLOUDIFY_TOSCA_ARTIFACTS_WORKER_PLUGIN);
            pluginDetails.putAll(plugin.getProperties());
            pluginDetails.put("name", pluginImplementation);
            pluginDetails.put("agent_plugin", Boolean.toString(agentPlugin));
            plugins.put(pluginImplementation, pluginDetails);

            Set<String> operations = Sets.newHashSet(theInterface.getOperations());
            for (String operation : operations) {
                // always add fully qualified name to operation
                operationToPlugin.put(interfaceDescription.getName() + "." + operation, pluginImplementation);

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
        node.put("plugins", plugins);
        node.put("operations", operationToPlugin);
    }

    private void setNodeSuperTypes(TypeTemplate typeTemplate, Map<String, Object> nodeExtraData) {
        nodeExtraData.put("super_types", typeTemplate.getSuperTypes());
    }

    private void setNodeFlattenedRelationships(TypeTemplate typeTemplate,
                                               String serviceTemplateName,
                                               Map<String, Object> nodeExtraData) {
        List<String> flattenedRelations = Lists.newArrayList();
        for (Map.Entry<String, Object> entry : typeTemplate.getRelationships().entrySet()) {
            flattenedRelations.add(extractFullTargetIdFromRelationship(serviceTemplateName, entry));
        }
        nodeExtraData.put("relationships", flattenedRelations);
    }

    private String extractFullTargetIdFromRelationship(String serviceTemplateName, Map.Entry<String, Object> entry) {
        String targetId = (String) entry.getValue();
        return serviceTemplateName + "." + targetId;
    }

}
