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
import com.google.common.io.Resources;
import org.testng.Assert;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
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

    protected URI readResource(String resource) {
        try {
            return Resources.getResource(resource).toURI();
        } catch (URISyntaxException e) {
            throw Throwables.propagate(e);
        }
    }

    protected Processed process(URI dslUri) {
        String processed = DSLProcessor.process(dslUri, POST_PROCESSOR);
        try {
            return OBJECT_MAPPER.readValue(processed, Processed.class);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    protected ObjectMapper getObjectMapper() {
        return OBJECT_MAPPER;
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
        public List<Node> getNodes() {
            return nodes;
        }
        public void setNodes(List<Node> nodes) {
            this.nodes = nodes;
        }
    }

    /**
     */
    public static class Node {
        String id;
        Map<String, Object> workflows;
        Map<String, Object> operations;
        Map<String, Object> properties;
        List<Object> relationships;

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

        public Map<String, Object> getOperations() {
            return operations;
        }

        public void setOperations(Map<String, Object> operations) {
            this.operations = operations;
        }

        public List<Object> getRelationships() {
            return relationships;
        }

        public void setRelationships(List<Object> relationships) {
            this.relationships = relationships;
        }

        public Map<String, Object> getProperties() {
            return properties;
        }

        public void setProperties(Map<String, Object> properties) {
            this.properties = properties;
        }
    }

}
