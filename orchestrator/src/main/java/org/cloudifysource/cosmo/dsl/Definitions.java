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

import java.util.Map;

/**
 * A class used to represent the top level definitions of the dsl.
 * Used internally only by the dsl processor.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class Definitions {

    private Map<String, Type> types;
    private Map<String, Relationship> relationships;
    private Map<String, Provider> providers;

    // TODO DSL currently this is a service template. should be extracted to its own type
    // once we introduce plans into it
    private Map<String, TypeTemplate> serviceTemplate;

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

    public Map<String, Provider> getProviders() {
        return providers;
    }

    public void setProviders(Map<String, Provider> providers) {
        this.providers = providers;
    }

    public Map<String, TypeTemplate> getServiceTemplate() {
        return serviceTemplate;
    }

    public void setServiceTemplate(Map<String, TypeTemplate> serviceTemplate) {
        this.serviceTemplate = serviceTemplate;
    }

}
