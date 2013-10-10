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
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.google.common.base.Throwables;
import org.testng.Assert;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 *
 * @author Dan Kilman
 * @since 0.1
 */
public abstract class AbstractDSLProcessorTest {

    private static final ObjectMapper OBJECT_MAPPER = newObjectMapper();
    private static final DSLPostProcessor POST_PROCESSOR = new PluginArtifactAwareDSLPostProcessor();

    protected Processed process(String dslLocation) {
        String processed = DSLProcessor.process(dslLocation, POST_PROCESSOR);
        try {
            return OBJECT_MAPPER.readValue(processed, Processed.class);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    protected static ObjectMapper newObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.setPropertyNamingStrategy(PropertyNamingStrategy.CAMEL_CASE_TO_LOWER_CASE_WITH_UNDERSCORES);
        mapper.setSerializationInclusion(JsonInclude.Include.NON_NULL);
        mapper.configure(SerializationFeature.INDENT_OUTPUT, true);
        return mapper;
    }

    protected Node findNode(List<Node> nodes, String id) {
        for (Node node : nodes) {
            if (id.equals(node.getId())) {
                return node;
            }
        }
        Assert.fail("Failed finding node: " + id);
        return null;
    }

    /**
     */
    public static class Processed {
        List<Node> nodes;
        Map<String, NodeExtra> nodesExtra;
        Map<String, Map<String, Policy>> policies;
        Map<String, org.cloudifysource.cosmo.dsl.RuleDefinition> rules;
        private Map<String, PolicyDefinition> policiesEvents;
        Map<String, Relationship> relationships;
        Map<String, Object> workflows;

        public List<Node> getNodes() {
            return nodes;
        }
        public void setNodes(List<Node> nodes) {
            this.nodes = nodes;
        }
        public Map<String, NodeExtra> getNodesExtra() {
            return nodesExtra;
        }

        public void setNodesExtra(Map<String, NodeExtra> nodesExtra) {
            this.nodesExtra = nodesExtra;
        }

        public Map<String, Map<String, Policy>> getPolicies() {
            return policies;
        }

        public void setPolicies(Map<String, Map<String, Policy>> policies) {
            this.policies = policies;
        }

        public Map<String, org.cloudifysource.cosmo.dsl.RuleDefinition> getRules() {
            return rules;
        }

        public void setRules(Map<String, org.cloudifysource.cosmo.dsl.RuleDefinition> rules) {
            this.rules = rules;
        }

        public void setPoliciesEvents(Map<String, PolicyDefinition> policiesEvents) {
            this.policiesEvents = policiesEvents;
        }

        public Map<String, PolicyDefinition> getPoliciesEvents() {
            return policiesEvents;
        }

        public Map<String, Relationship> getRelationships() {
            return relationships;
        }

        public void setRelationships(Map<String, Relationship> relationships) {
            this.relationships = relationships;
        }

        public Map<String, Object> getWorkflows() {
            return workflows;
        }

        public void setWorkflows(Map<String, Object> workflows) {
            this.workflows = workflows;
        }
    }

    /**
     */
    public static class Node {
        String id;
        Map<String, Object> workflows;
        Map<String, String> operations;
        Map<String, Object> properties;
        List<ProcessedRelationshipTemplate> relationships;
        Map<String, Object> plugins;
        Map<String, Policy> policies;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public Map<String, Object> getWorkflows() {
            return workflows;
        }

        public void setWorkflows(Map<String, Object> workflows) {
            this.workflows = workflows;
        }

        public Map<String, String> getOperations() {
            return operations;
        }

        public void setOperations(Map<String, String> operations) {
            this.operations = operations;
        }

        public List<ProcessedRelationshipTemplate> getRelationships() {
            return relationships;
        }

        public void setRelationships(List<ProcessedRelationshipTemplate> relationships) {
            this.relationships = relationships;
        }

        public Map<String, Object> getProperties() {
            return properties;
        }

        public void setProperties(Map<String, Object> properties) {
            this.properties = properties;
        }

        public Map<String, Object> getPlugins() {
            return plugins;
        }

        public void setPlugins(Map<String, Object> plugins) {
            this.plugins = plugins;
        }

        public Map<String, Policy> getPolicies() {
            return policies;
        }
    }

    /**
     */
    public static class Policy {
        private List<Rule> rules;

        public void setRules(List<Rule> rules) {
            this.rules = rules;
        }

        public List<Rule> getRules() {
            return rules;
        }
    }

    /**
     */
    public static class Rule {
        private String type;
        private Map<String, Object> properties;

        public void setType(String type) {
            this.type = type;
        }

        public void setProperties(Map<String, Object> properties) {
            this.properties = properties;
        }

        public String getType() {
            return type;
        }

        public Map<String, Object> getProperties() {
            return properties;
        }
    }

    /**
     */
    public static class NodeExtra {
        List<String> superTypes;
        List<String> relationships;

        public List<String> getSuperTypes() {
            return superTypes;
        }
        public void setSuperTypes(List<String> superTypes) {
            this.superTypes = superTypes;
        }
        public List<String> getRelationships() {
            return relationships;
        }
        public void setRelationships(List<String> relationships) {
            this.relationships = relationships;
        }

    }

    /**
     */
    public static class ProcessedRelationshipTemplate {
        String type;
        String targetId;
        String plugin;
        String bindAt;
        String runOnNode;
        private Interface anInterface;
        private String workflow;

        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public String getTargetId() {
            return targetId;
        }

        public void setTargetId(String targetId) {
            this.targetId = targetId;
        }

        public String getPlugin() {
            return plugin;
        }

        public void setPlugin(String plugin) {
            this.plugin = plugin;
        }

        public String getBindAt() {
            return bindAt;
        }

        public void setBindAt(String bindAt) {
            this.bindAt = bindAt;
        }

        public String getRunOnNode() {
            return runOnNode;
        }

        public void setRunOnNode(String runOnNode) {
            this.runOnNode = runOnNode;
        }

        public Interface getInterface() {
            return anInterface;
        }

        public void setInterface(Interface anInterface) {
            this.anInterface = anInterface;
        }

        public String getWorkflow() {
            return workflow;
        }

        public void setWorkflow(String workflow) {
            this.workflow = workflow;
        }
    }

}
