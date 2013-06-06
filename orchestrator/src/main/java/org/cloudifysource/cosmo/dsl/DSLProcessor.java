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
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.dsl.tree.Node;
import org.cloudifysource.cosmo.dsl.tree.Tree;
import org.cloudifysource.cosmo.dsl.tree.Visitor;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * Processes dsl in json format into a json form suitable for ruote consumption.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class DSLProcessor {

    /**
     * @param dsl The dsl in its declarative form
     * @return A processed json dsl to be used by the workflow engine.
     */
    public static String process(String dsl) {

        try {

            ObjectMapper mapper = newObjectMapper();
            Definitions definitions = parseRawDsl(mapper, dsl);

            Tree<String> typeNameHierarchyTree = buildTypeNameHierarchyTree(definitions);

            Map<String, Type> populatedTypes = buildPopulatedTypesMap(definitions, typeNameHierarchyTree);

            Map<String, TypeTemplate> populatedTemplates =
                    buildPopulatedTemplatesMap(definitions, populatedTypes);

            Map<String, Object> plan = buildPlan(populatedTemplates);

            return mapper.writeValueAsString(plan);

        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private static Map<String, Object> buildPlan(Map<String, TypeTemplate> populatedTemplates) {
        Map<String, Object> plan = Maps.newHashMap();
        List<Object> nodes = Lists.newArrayList();
        for (TypeTemplate typeTemplate : populatedTemplates.values()) {
            Map<String, Object> node = Maps.newHashMap();
            node.put("id", typeTemplate.getName());
            node.put("properties", typeTemplate.getProperties());
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
            Map<String, String> workflows = Maps.newHashMap();
            workflows.put("init", String.format("define %s_init\n echo ' -> %s_init'\n", typeTemplate.getName(),
                    typeTemplate.getName()));
            node.put("workflows", workflows);
            nodes.add(node);
        }
        plan.put("nodes", nodes);
        return plan;
    }

    private static Map<String, TypeTemplate> buildPopulatedTemplatesMap(Definitions definitions,
                                                                        Map<String, Type> populatedTypes) {
        final Map<String, TypeTemplate> populatedTemplates = Maps.newHashMap();
        for (Map.Entry<String, TypeTemplate> entry : definitions.getServiceTemplate().entrySet()) {
            String templateName = entry.getKey();
            TypeTemplate typeTemplate = entry.getValue();

            TypeTemplate populatedTemplate = new TypeTemplate();
            Type typeTemplateParentType = populatedTypes.get(typeTemplate.getType());
            Preconditions.checkArgument(typeTemplateParentType != null, "Missing type %s for %s", templateName,
                    typeTemplate.getType());
            populatedTemplate.inheritPropertiesFrom(typeTemplateParentType);
            populatedTemplate.inheritPropertiesFrom(typeTemplate);
            populatedTemplate.setName(templateName);
            populatedTemplates.put(templateName, populatedTemplate);
        }
        return populatedTemplates;
    }

    private static Map<String, Type> buildPopulatedTypesMap(final Definitions definitions, Tree<String> tree) {
        final Map<String, Type> populatedTypes = Maps.newHashMap();
        tree.traverseParentThenChildren(new Visitor<String>() {
            @Override
            public void visit(Node<String> node) {
                String parentTypeName = node.getParentValue();
                Type parentType = populatedTypes.get(parentTypeName);
                if (parentType == null) {
                    populatedTypes.put(Type.ROOT_NODE_TYPE_NAME, Type.ROOT_NODE_TYPE);
                    return;
                }
                Type populatedType = new Type();
                populatedType.inheritPropertiesFrom(parentType);
                String typeName = node.getValue();
                Type type = definitions.getTypes().get(typeName);
                populatedType.inheritPropertiesFrom(type);
                populatedType.setName(typeName);
                populatedTypes.put(typeName, populatedType);
            }
        });
        return populatedTypes;
    }

    private static Tree<String> buildTypeNameHierarchyTree(Definitions definitions) {
        Tree<String> tree = new Tree<>(Type.ROOT_NODE_TYPE_NAME);
        for (String typeName : definitions.getTypes().keySet()) {
            tree.addNode(typeName);
        }
        for (Map.Entry<String, Type> entry : definitions.getTypes().entrySet()) {
            String typeName = entry.getKey();
            Type type = entry.getValue();
            String parentTypeName = type.getType();
            tree.setParentChildRelationship(parentTypeName, typeName);
        }
        tree.validateLegalTree();
        return tree;
    }

    private static Definitions parseRawDsl(ObjectMapper mapper, String dsl) throws IOException {

        Map<String, Definitions> topLevel = mapper.readValue(dsl,
                new TypeReference<Map<String, Definitions>>() { });

        Definitions definitions = topLevel.get("definitions");
        Preconditions.checkArgument(definitions != null, "Missing definitions in provided dsl");

        setNames(definitions.getProviders());
        setNames(definitions.getRelationships());
        setNames(definitions.getServiceTemplate());
        setNames(definitions.getTypes());
        for (Type type : definitions.getTypes().values()) {
            setNames(type.getInterfaces());
        }
        for (Type type : definitions.getServiceTemplate().values()) {
            setNames(type.getInterfaces());
        }
        return definitions;
    }

    private static void setNames(Map<String, ? extends Named> namedEntries) {
        for (Map.Entry<String, ? extends Named> entry : namedEntries.entrySet()) {
            entry.getValue().setName(entry.getKey());
        }
    }

    private static ObjectMapper newObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        mapper.configure(SerializationFeature.INDENT_OUTPUT, true);
        return mapper;
    }

}
