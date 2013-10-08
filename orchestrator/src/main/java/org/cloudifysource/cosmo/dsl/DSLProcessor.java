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

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import com.google.common.base.Preconditions;
import com.google.common.base.Strings;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.dsl.resource.DSLResource;
import org.cloudifysource.cosmo.dsl.resource.ImportsContext;
import org.cloudifysource.cosmo.dsl.resource.ResourceLoadingContext;
import org.cloudifysource.cosmo.dsl.resource.ResourcesLoader;
import org.cloudifysource.cosmo.dsl.tree.Node;
import org.cloudifysource.cosmo.dsl.tree.Tree;
import org.cloudifysource.cosmo.dsl.tree.Visitor;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.IOException;
import java.net.URL;
import java.util.List;
import java.util.Map;

/**
 * Processes dsl in json format into a json form suitable for ruote consumption.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessor {

    private static final Logger LOG = LoggerFactory.getLogger(DSLProcessor.class);
    private static final ObjectMapper JSON_OBJECT_MAPPER = newObjectMapper(new JsonFactory());
    private static final ObjectMapper YAML_OBJECT_MAPPER = newObjectMapper(new YAMLFactory());

    private static final String ALIAS_MAPPING_RESOURCE = "org/cloudifysource/cosmo/dsl/alias-mappings.yaml";

    /**
     * @param dslLocation A string pointing to the dsl in its declarative form. Can be either a file system path,
     *                    url or classpath locations.
     * @return A processed json dsl to be used by the workflow engine.
     */
    public static String process(String dslLocation, DSLPostProcessor postProcessor) {

        LOG.debug("Starting dsl processing: {}", dslLocation);

        try {
            final String baseLocation = ResourceLocationHelper.getParentLocation(dslLocation);
            DSLResource loadedDsl = ResourcesLoader.load(dslLocation, new ImportsContext(baseLocation));
            LOG.debug("Loaded dsl:\n{}", loadedDsl.getContent());

            ImportsContext importContext = new ImportsContext(
                    ResourceLocationHelper.createLocationString(baseLocation, "definitions"));
            importContext.addMapping(loadAliasMapping());
            Definitions definitions = parseDslAndHandleImports(loadedDsl, importContext);

            Map<String, Type> populatedTypes = buildPopulatedTypesMap(definitions.getTypes());
            Map<String, Plugin> populatedArtifacts = buildPopulatedArtifactsMap(definitions.getPlugins());
            Map<String, Relationship> populatedRelationships = buildPopulatedRelationshipsMap(
                    definitions.getRelationships());

            Map<String, ApplicationTemplate> populatedServiceTemplates =
                    buildPopulatedServiceTemplatesMap(definitions, populatedTypes);

            Map<String, TypeTemplate> nodeTemplates = extractNodeTemplates(definitions);
            validatePolicies(nodeTemplates, definitions.getPolicies());
            validateRelationships(nodeTemplates, populatedRelationships);

            Map<String, Object> plan = postProcessor.postProcess(
                    definitions,
                    populatedServiceTemplates,
                    populatedArtifacts,
                    populatedRelationships);

            if (!Strings.isNullOrEmpty(definitions.getGlobalPlan())) {
                String globalPlanResourcePath = definitions.getGlobalPlan();
                ResourceLoadingContext resourceLoadingContext = new ResourceLoadingContext(baseLocation);
                resourceLoadingContext.setContextLocation(
                        ResourceLocationHelper.createLocationString(baseLocation, "workflows"));
                DSLResource globalPlanResource = ResourcesLoader.load(globalPlanResourcePath, resourceLoadingContext);
                String globalPlanContent = globalPlanResource.getContent();
                plan.put("global_workflow", globalPlanContent);
                LOG.debug("Loaded global plan: \n{}", globalPlanContent);
            }

            String result = JSON_OBJECT_MAPPER.writeValueAsString(plan);
            LOG.debug("Processed dsl is: {}", result);
            return result;

        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private static void validateRelationships(Map<String, TypeTemplate> nodeTemplates,
                                              Map<String, Relationship> populatedRelationships) {
        for (Map.Entry<String, TypeTemplate> templateEntry : nodeTemplates.entrySet()) {
            String typeTemplateName = templateEntry.getKey();
            TypeTemplate template = templateEntry.getValue();
            String serviceTemplate = typeTemplateName.split("\\.")[0];
            for (RelationshipTemplate relationshipTemplate : template.getRelationships()) {
                String targetName = String.format("%s.%s", serviceTemplate, relationshipTemplate.getTarget());
                Preconditions.checkArgument(populatedRelationships.containsKey(relationshipTemplate.getType()),
                                            "No relationship of type [%s] found for node [%s]",
                                            relationshipTemplate.getType(), template.getName());
                Preconditions.checkArgument(nodeTemplates.containsKey(targetName),
                        "No node template [%s] found for relationship [%s] in node [%s]",
                        targetName, relationshipTemplate.getType(), typeTemplateName);
            }
        }
    }

    private static void validatePolicies(Map<String, TypeTemplate> nodeTemplates, Policies policies) {
        for (TypeTemplate template : nodeTemplates.values()) {
            if (template.getPolicies() == null) {
                return;
            }
            for (Map.Entry<String, Policy> policyEntry : template.getPolicies().entrySet()) {
                Preconditions.checkArgument(
                        policies.getTypes().containsKey(
                                policyEntry.getKey()),
                        "Policy not defined [%s] in template: %s - available policies: %s",
                        template.getName(), policyEntry, policies.getTypes());
                final Policy policy = policyEntry.getValue();
                for (Rule rule : policy.getRules()) {
                    Preconditions.checkArgument(policies.getRules().containsKey(rule.getType()),
                            "Unknown rule type [%s] for rule: '%s' in template: %s", rule.getType(),
                            rule, template.getName());
                }
            }
        }
    }

    private static Map<String, TypeTemplate> extractNodeTemplates(Definitions definitions) {
        final Map<String, TypeTemplate> nodeTemplates = Maps.newHashMap();
        final ApplicationTemplate applicationTemplate = definitions.getApplicationTemplate();
        for (TypeTemplate typeTemplate : applicationTemplate.getTopology()) {
            nodeTemplates.put(
                    String.format("%s.%s", applicationTemplate.getName(), typeTemplate.getName()), typeTemplate);
        }
        return nodeTemplates;
    }


    private static Map<String, ApplicationTemplate> buildPopulatedServiceTemplatesMap(
            Definitions definitions,
            Map<String, Type> populatedTypes) {
        final Map<String, ApplicationTemplate> populatedServiceTemplates = Maps.newHashMap();
        final ApplicationTemplate applicationTemplate = definitions.getApplicationTemplate();

        List<TypeTemplate> populatedTopology = buildPopulatedTypeTemplatesMap(
                applicationTemplate.getTopology(),
                populatedTypes);

        ApplicationTemplate populatedApplicationTemplate = new ApplicationTemplate();
        populatedApplicationTemplate.setName(applicationTemplate.getName());
        populatedApplicationTemplate.setTopology(populatedTopology);

        populatedServiceTemplates.put(applicationTemplate.getName(), populatedApplicationTemplate);

        return populatedServiceTemplates;
    }

    private static List<TypeTemplate> buildPopulatedTypeTemplatesMap(
            List<TypeTemplate> topology,
            Map<String, Type> populatedTypes) {
        final Map<String, TypeTemplate> populatedTemplates = Maps.newHashMap();
        for (TypeTemplate template : topology) {
            Type typeTemplateParentType = populatedTypes.get(template.getDerivedFrom());
            Preconditions.checkArgument(typeTemplateParentType != null, "Missing type %s for %s", template.getName(),
                    template.getDerivedFrom());
            TypeTemplate populatedTemplate = (TypeTemplate) template.newInstanceWithInheritance(
                    typeTemplateParentType);

            populatedTemplates.put(template.getName(), populatedTemplate);
        }
        return Lists.newArrayList(populatedTemplates.values());
    }

    private static Map<String, Type> buildPopulatedTypesMap(Map<String, Type> types) {
        return buildPopulatedMap(Type.ROOT_NODE_TYPE_NAME,
                                 Type.ROOT_NODE_TYPE,
                                 types);
    }

    private static Map<String, Plugin> buildPopulatedArtifactsMap(Map<String, Plugin> artifacts) {
        return buildPopulatedMap(Plugin.ROOT_PLUGIN_NAME,
                                 Plugin.ROOT_PLUGIN,
                                 artifacts);
    }

    private static Map<String, Relationship> buildPopulatedRelationshipsMap(Map<String, Relationship> relationships) {
        return buildPopulatedMap(Relationship.ROOT_RELATIONSHIP_NAME,
                                 Relationship.ROOT_RELATIONSHIP,
                                 relationships);
    }

    private static <T extends InheritedDefinition> Map<String, T> buildPopulatedMap(
            final String rootName,
            final T root,
            final Map<String, T> inheritedDefinitions) {
        Tree<String> nameHierarchyTree = buildNameHierarchyTree(inheritedDefinitions, rootName);
        final Map<String, T> populatedInheritedDefinitions = Maps.newHashMap();
        nameHierarchyTree.traverseParentThenChildren(new Visitor<String>() {
            @Override
            public void visit(Node<String> node) {
                String parentName = node.getParentValue();
                T parentInheritedDefinition = populatedInheritedDefinitions.get(parentName);
                if (parentInheritedDefinition == null) {
                    populatedInheritedDefinitions.put(rootName, root);
                    return;
                }
                String name = node.getValue();
                T inheritedDefinition = inheritedDefinitions.get(name);
                T populatedInheritedDefinition =
                        (T) inheritedDefinition.newInstanceWithInheritance(parentInheritedDefinition);
                populatedInheritedDefinitions.put(name, populatedInheritedDefinition);
            }
        });

        return populatedInheritedDefinitions;
    }

    private static Tree<String> buildNameHierarchyTree(
            Map<String, ? extends InheritedDefinition> inheritedDefinitions,
            String rootName
    ) {
        Tree<String> tree = new Tree<>(rootName);
        for (String artifactName : inheritedDefinitions.keySet()) {
            tree.addNode(artifactName);
        }
        for (Map.Entry<String, ? extends InheritedDefinition> entry : inheritedDefinitions.entrySet()) {
            String artifactName = entry.getKey();
            InheritedDefinition type = entry.getValue();
            String parentArtifactName = type.getDerivedFrom();
            tree.setParentChildRelationship(parentArtifactName, artifactName);
        }
        tree.validateLegalTree();
        return tree;
    }

    private static Definitions parseDslAndHandleImports(DSLResource dsl, ImportsContext context) {
        final Definitions definitions = parseRawDsl(dsl.getContent());
        String currentContext = context.getContextLocation();
        LOG.debug("Loading imports for dsl: {} [imports={}]", dsl.getLocation(), definitions.getImports());
        for (String definitionImport : definitions.getImports()) {

            DSLResource importedDsl = ResourcesLoader.load(definitionImport, context);

            LOG.debug("Loaded import: {} [uri={}]", definitionImport, importedDsl.getLocation());

            if (context.isImported(importedDsl.getLocation())) {
                LOG.debug("Filtered import: {} (already imported)", definitionImport);
                continue;
            }
            context.addImport(importedDsl.getLocation());

            context.setContextLocation(ResourceLocationHelper.getParentLocation(importedDsl.getLocation()));
            Definitions importedDefinitions = parseDslAndHandleImports(importedDsl, context);
            context.setContextLocation(currentContext);

            copyDefinitions(importedDefinitions.getTypes(), definitions.getTypes());
            copyDefinitions(importedDefinitions.getPlugins(), definitions.getPlugins());
            copyDefinitions(importedDefinitions.getRelationships(), definitions.getRelationships());
            copyDefinitions(importedDefinitions.getInterfaces(), definitions.getInterfaces());
            copyMapNoOverride(importedDefinitions.getPolicies().getRules(), definitions.getPolicies().getRules());
            copyMapNoOverride(importedDefinitions.getPolicies().getTypes(), definitions.getPolicies().getTypes());
            copyGlobalPlan(importedDefinitions, definitions);
        }

        return definitions;
    }

    private static void copyGlobalPlan(Definitions importedDefinitions, Definitions definitions) {
        if (!Strings.isNullOrEmpty(importedDefinitions.getGlobalPlan())) {
            if (!Strings.isNullOrEmpty(definitions.getGlobalPlan())) {
                throw new IllegalArgumentException("Cannot override definitions of global plan");
            }
            definitions.setGlobalPlan(importedDefinitions.getGlobalPlan());
        }
    }

    private static <T extends Definition> void copyDefinitions(Map<String, T> copyFromDefinitions,
                                                               Map<String, T> copyToDefinitions) {
        copyMapNoOverride(copyFromDefinitions, copyToDefinitions);
    }

    private static <T extends Object> void copyMapNoOverride(Map<String, T> copyFromDefinitions,
                                                             Map<String, T> copyToDefinitions) {
        for (Map.Entry<String, T> entry : copyFromDefinitions.entrySet()) {
            String name = entry.getKey();
            T definition = entry.getValue();
            if (copyToDefinitions.containsKey(name)) {
                throw new IllegalArgumentException("Cannot override definition of [" + name + "]");
            }
            copyToDefinitions.put(name, definition);
        }
    }

    private static Definitions parseRawDsl(String dsl) {
        try {
            final ObjectMapper objectMapper = dsl.startsWith("{") ? JSON_OBJECT_MAPPER : YAML_OBJECT_MAPPER;
            Definitions definitions = objectMapper.readValue(dsl, Definitions.class);
            if (definitions == null) {
                throw new IllegalArgumentException("Invalid DSL.");
            }

            setNames(definitions.getPlugins());
            setNames(definitions.getRelationships());
            setNames(definitions.getTypes());
            setNames(definitions.getInterfaces());

            return definitions;
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private static void setNames(Map<String, ? extends Definition> namedEntries) {
        for (Map.Entry<String, ? extends Definition> entry : namedEntries.entrySet()) {
            entry.getValue().setName(entry.getKey());
        }
    }

    private static ObjectMapper newObjectMapper(JsonFactory factory) {
        ObjectMapper mapper = new ObjectMapper(factory);
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        mapper.configure(SerializationFeature.INDENT_OUTPUT, true);
        return mapper;
    }

    private static Map<String, String> loadAliasMapping() {
        URL mappingResource = Resources.getResource(ALIAS_MAPPING_RESOURCE);
        try {
            return YAML_OBJECT_MAPPER.readValue(mappingResource, new TypeReference<Map<String, String>>() { });
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private static String loadGlobalPlan(String globalPlanResourcePath) {
        final String globalPlanBaseLocation = ResourceLocationHelper.getParentLocation(globalPlanResourcePath);
        ResourceLoadingContext resourceLoadingContext = new ResourceLoadingContext(globalPlanBaseLocation);
        DSLResource globalPlanResource = ResourcesLoader.load(globalPlanResourcePath, resourceLoadingContext);
        return globalPlanResource.getContent();
    }

}
