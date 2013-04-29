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
 *******************************************************************************/
package org.cloudifysource.cosmo.orchestrator.recipe;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * JSON recipe representation.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class JsonRecipe {

    private final Map<String, Map<String, Object>> components;

    public static JsonRecipe load(String recipe) throws IOException {
        ObjectMapper mapper = new ObjectMapper();
        final Map<String, Map<String, Object>> components =
                mapper.readValue(recipe, new TypeReference<Map<String, Map<String, Object>>>() {
                });
        return new JsonRecipe(components);
    }

    private JsonRecipe(Map<String, Map<String, Object>> components) {
        this.components = components;
    }

    public Optional<Map<String, Object>> get(String name) {
        if (!components.containsKey(name))
            return Optional.absent();

        final Map<String, Object> map = components.get(name);
        map.put("name", name);

        final List<String> resourcesNames = getComponentResourcesNames(map);
        final List<Map<String, Object>> resources = Lists.newLinkedList();
        for (String resourceName : resourcesNames) {
            resources.add(getResource(resourceName));
        }
        map.put("resources", resources);
        return Optional.of(map);
    }

    private Map<String, Object> getResource(String resourceName) {
        Preconditions.checkArgument(components.containsKey(resourceName));
        final Map<String, Object> resource = components.get(resourceName);
        Preconditions.checkArgument(resource.containsKey("type"));
        Preconditions.checkArgument("resource".equals(resource.get("type")));
        resource.put("name", resourceName);
        return resource;
    }

    public List<String> getComponentResourcesNames(Map<String, Object> component) {
        final List<String> resources = Lists.newLinkedList();
        getComponentResourcesNamesImpl(component, resources);
        return resources;
    }

    private void getComponentResourcesNamesImpl(Map<String, Object> component, List<String> resourcesNames) {
        final String type = (String) component.get("type");
        if (type != null) {
            final Map<String, Object> parentComponent = components.get(type);
            if (parentComponent != null) {
                getComponentResourcesNamesImpl(parentComponent, resourcesNames);
            }
        }
        final List<?> resources = (List<?>) component.get("resources");
        if (resources != null) {
            for (Object resource : resources) {
                resourcesNames.add(resource.toString());
            }
        }
    }

}
