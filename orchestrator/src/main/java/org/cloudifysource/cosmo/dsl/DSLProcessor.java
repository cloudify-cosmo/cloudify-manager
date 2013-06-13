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
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.dsl.tree.Node;
import org.cloudifysource.cosmo.dsl.tree.Tree;
import org.cloudifysource.cosmo.dsl.tree.Visitor;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.io.IOException;
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

    /**
     * @param dsl The dsl in its declarative form
     * @return A processed json dsl to be used by the workflow engine.
     */
    public static String process(String dsl, DSLPostProcessor postProcessor) {

        LOG.debug("Starting dsl processing");

        try {

            Definitions definitions = parseDslAndHandleImports(dsl, new ImportContext());

            Map<String, Type> populatedTypes = buildPopulatedTypesMap(definitions.getTypes());
            Map<String, Artifact> populatedArtifacts = buildPopulatedArtifactsMap(definitions.getArtifacts());
            Map<String, Relationship> populatedRelationships = buildPopulatedRelationshipsMap(
                    definitions.getRelationships());

            Map<String, TypeTemplate> populatedTypeTemplates =
                    buildPopulatedTemplatesMap(definitions, populatedTypes);

            Map<String, Object> plan = postProcessor.postProcess(
                    definitions,
                    populatedTypeTemplates,
                    populatedArtifacts);

            String result = JSON_OBJECT_MAPPER.writeValueAsString(plan);
            LOG.debug("Processed dsl is: {}", result);
            return result;

        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private static Map<String, TypeTemplate> buildPopulatedTemplatesMap(Definitions definitions,
                                                                        Map<String, Type> populatedTypes) {
        final Map<String, TypeTemplate> populatedTemplates = Maps.newHashMap();
        for (Map.Entry<String, TypeTemplate> entry : definitions.getServiceTemplate().entrySet()) {
            String templateName = entry.getKey();
            TypeTemplate typeTemplate = entry.getValue();
            Type typeTemplateParentType = populatedTypes.get(typeTemplate.getDerivedFrom());
            Preconditions.checkArgument(typeTemplateParentType != null, "Missing type %s for %s", templateName,
                    typeTemplate.getDerivedFrom());
            TypeTemplate populatedTemplate = (TypeTemplate) typeTemplate.newInstanceWithInheritance(
                    typeTemplateParentType);

            populatedTemplates.put(templateName, populatedTemplate);
        }
        return populatedTemplates;
    }

    private static Map<String, Type> buildPopulatedTypesMap(Map<String, Type> types) {
        return buildPopulatedMap(Type.ROOT_NODE_TYPE_NAME,
                                 Type.ROOT_NODE_TYPE,
                                 types);
    }

    private static Map<String, Artifact> buildPopulatedArtifactsMap(Map<String, Artifact> artifacts) {
        return buildPopulatedMap(Artifact.ROOT_ARTIFACT_NAME,
                                 Artifact.ROOT_ARTIFACT,
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

    private static Definitions parseDslAndHandleImports(String dsl, ImportContext context) {

        Definitions definitions = parseRawDsl(dsl);
        for (String definitionImport : definitions.getImports()) {
            if (context.isImported(definitionImport)) {
                continue;
            }
            context.addImport(definitionImport);

            String importedDsl = ImportsLoader.load(definitionImport);
            Definitions importedDefinitions = parseDslAndHandleImports(importedDsl, context);

            if (!importedDefinitions.getServiceTemplate().isEmpty()) {
                throw new IllegalArgumentException("Cannot define a service_templates element in an imported " +
                        "definition [" + definitionImport + "]");
            }

            copyDefinitions(importedDefinitions.getTypes(), definitions.getTypes());
            copyDefinitions(importedDefinitions.getArtifacts(), definitions.getArtifacts());
            copyDefinitions(importedDefinitions.getRelationships(), definitions.getRelationships());
            copyDefinitions(importedDefinitions.getInterfaces(), definitions.getInterfaces());
            copyPlans(importedDefinitions.getPlans(), definitions.getPlans());

        }

        return definitions;
    }

    private static <T extends Definition> void copyDefinitions(Map<String, T> copyFromDefinitions,
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

    private static void copyPlans(Map<String, Plan> copyFromPlans,
                                  Map<String, Plan> copyToPlans) {
        // TODO DSL need to define semantics and
        // add some sort of validation to this copy phase.
        // Currently the semantics are not very clear.
        // The first plan to show up in the import phase will be
        // the one to "win". Where 'first' is not clearly defined.
        for (Map.Entry<String, Plan> entry : copyFromPlans.entrySet()) {
            String name = entry.getKey();
            Plan copiedPlan = entry.getValue();

            if (!copyToPlans.containsKey(name)) {
                copyToPlans.put(name, copiedPlan);
            } else {
                Plan currentPlan = copyToPlans.get(name);
                if (currentPlan.getInit().isEmpty()) {
                    currentPlan.setInit(copiedPlan.getInit());
                }
            }
        }
    }

    private static Definitions parseRawDsl(String dsl) {
        try {
            final ObjectMapper objectMapper = dsl.startsWith("{") ? JSON_OBJECT_MAPPER : YAML_OBJECT_MAPPER;
            TopLevel topLevel = objectMapper.readValue(dsl, TopLevel.class);
            Definitions definitions = topLevel.getDefinitions();
            if (definitions == null) {
                throw new IllegalArgumentException("Invalid DSL - does not contain definitions");
            }

            setNames(definitions.getArtifacts());
            setNames(definitions.getPlans());
            setNames(definitions.getRelationships());
            setNames(definitions.getServiceTemplate());
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

}
