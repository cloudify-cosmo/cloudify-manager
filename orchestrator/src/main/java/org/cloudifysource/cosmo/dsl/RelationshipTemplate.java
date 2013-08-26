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

import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;

import java.util.List;
import java.util.Map;

/**
 * Data container for a relationship template in a node template of the dsl.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class RelationshipTemplate {

    private String type;
    private String target;
    private List<Object> postTargetStart = Lists.newArrayList();
    private List<Object> postSourceStart = Lists.newArrayList();

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public List<Object> getPostTargetStart() {
        return postTargetStart;
    }

    public void setPostTargetStart(List<Object> postTargetStart) {
        this.postTargetStart = postTargetStart;
    }

    public List<Object> getPostSourceStart() {
        return postSourceStart;
    }

    public void setPostSourceStart(List<Object> postSourceStart) {
        this.postSourceStart = postSourceStart;
    }

    /**
     */
    static class ExecutionListItem {
        private final String operation;
        private final String outputField;
        ExecutionListItem(String operation, String outputField) {
            this.operation = operation;
            this.outputField = outputField;
        }
        String getOperation() {
            return operation;
        }
        String getOutputField() {
            return outputField;
        }
        static Map<String, String> fromObject(Object rawItem) {
            if (rawItem instanceof String) {
                return new ExecutionListItem((String) rawItem, "").toMap();
            } else if (rawItem instanceof Map) {
                Map.Entry<String, String> entry =
                        (Map.Entry<String, String>) ((Map) rawItem).entrySet().iterator().next();
                return new ExecutionListItem(entry.getKey(), entry.getValue()).toMap();
            } else {
                throw new IllegalArgumentException("Cannot convert [" + rawItem + "] to an execution list item");
            }
        }
        Map<String, String> toMap() {
            return ImmutableMap.<String, String>builder().put("operation", operation)
                                                         .put("output_field", outputField)
                                                         .build();
        }
    }
}
