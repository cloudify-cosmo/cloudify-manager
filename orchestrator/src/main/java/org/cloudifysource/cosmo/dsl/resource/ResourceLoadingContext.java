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

package org.cloudifysource.cosmo.dsl.resource;

import com.google.common.collect.Maps;

import java.util.Map;

/**
 * Contains context used for different resource loading phases {@link org.cloudifysource.cosmo.dsl.DSLProcessor}.
 * (imports, workflows, etc...)
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class ResourceLoadingContext {

    private final Map<String, String> aliasMappings = Maps.newHashMap();
    private final String baseLocation;
    private String contextLocation;

    public ResourceLoadingContext(String baseLocation) {
        this.baseLocation = baseLocation;
        this.contextLocation = baseLocation;
    }

    public String getBaseLocation() {
        return baseLocation;
    }

    public String getContextLocation() {
        return contextLocation;
    }

    public void setContextLocation(String contextLocation) {
        this.contextLocation = contextLocation;
    }

    public String getMapping(String alias) {
        String mapping = aliasMappings.get(alias);
        return mapping != null ? mapping : alias;
    }

    public void addMapping(Map<String, String> aliasMappings) {
        this.aliasMappings.putAll(aliasMappings);
    }

}
