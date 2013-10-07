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

import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

import java.util.List;
import java.util.Map;

/**
 * A class used to represent the top level element of the dsl.
 * Used internally only by the dsl processor.
 * @author Dan Kilman
 * @since 0.1
 */
public class Definitions {

    private List<String> imports = Lists.newArrayList();
    private ApplicationTemplate applicationTemplate = new ApplicationTemplate();
    private Map<String, Type> types = Maps.newHashMap();
    private Map<String, Interface> interfaces = Maps.newHashMap();
    private Map<String, Plugin> plugins = Maps.newHashMap();
    private Map<String, Relationship> relationships = Maps.newHashMap();
    private Map<String, Workflow> workflows = Maps.newHashMap();
    private Policies policies = new Policies();
    private String globalPlan;

    public Map<String, Type> getTypes() {
        return types;
    }

    public void setTypes(Map<String, Type> types) {
        this.types = types;
    }

    public Map<String, Relationship> getRelationships() {
        return relationships;
    }

    public void setRelationships(Map<String, Relationship> relationships) {
        this.relationships = relationships;
    }

    public ApplicationTemplate getApplicationTemplate() {
        return applicationTemplate;
    }

    public void setApplicationTemplate(ApplicationTemplate applicationTemplate) {
        this.applicationTemplate = applicationTemplate;
    }

    public Map<String, Interface> getInterfaces() {
        return interfaces;
    }

    public void setInterfaces(Map<String, Interface> interfaces) {
        this.interfaces = interfaces;
    }

    public Map<String, Plugin> getPlugins() {
        return plugins;
    }

    public void setPlugins(Map<String, Plugin> plugins) {
        this.plugins = plugins;
    }

    public Map<String, Workflow> getWorkflows() {
        return workflows;
    }

    public void setWorkflows(Map<String, Workflow> workflows) {
        this.workflows = workflows;
    }

    public List<String> getImports() {
        return imports;
    }

    public void setImports(List<String> imports) {
        this.imports = imports;
    }

    public String getGlobalPlan() {
        return globalPlan;
    }

    public void setGlobalPlan(String globalPlan) {
        this.globalPlan = globalPlan;
    }

    public Policies getPolicies() {
        return policies;
    }

    public void setPolicies(Policies policies) {
        this.policies = policies;
    }


}
