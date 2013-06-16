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
 * A class used to represent the definitions of the dsl.
 * Used internally only by the dsl processor.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Definitions {

    private List<String> imports = Lists.newArrayList();
    private Map<String, ServiceTemplate> serviceTemplates = Maps.newHashMap();
    private Map<String, Type> types = Maps.newHashMap();
    private Map<String, Interface> interfaces = Maps.newHashMap();
    private Map<String, Artifact> artifacts = Maps.newHashMap();
    private Map<String, Relationship> relationships = Maps.newHashMap();
    private Map<String, Plan> plans = Maps.newHashMap();

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

    public Map<String, ServiceTemplate> getServiceTemplates() {
        return serviceTemplates;
    }

    public void setServiceTemplates(Map<String, ServiceTemplate> serviceTemplates) {
        this.serviceTemplates = serviceTemplates;
    }

    public Map<String, Interface> getInterfaces() {
        return interfaces;
    }

    public void setInterfaces(Map<String, Interface> interfaces) {
        this.interfaces = interfaces;
    }

    public Map<String, Artifact> getArtifacts() {
        return artifacts;
    }

    public void setArtifacts(Map<String, Artifact> artifacts) {
        this.artifacts = artifacts;
    }

    public Map<String, Plan> getPlans() {
        return plans;
    }

    public void setPlans(Map<String, Plan> plans) {
        this.plans = plans;
    }

    public List<String> getImports() {
        return imports;
    }

    public void setImports(List<String> imports) {
        this.imports = imports;
    }
}
