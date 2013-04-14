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

import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * A {@link Recipe} implementation created from a Yaml recipe.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class YamlRecipe implements Recipe {

    private Map<String, Appliance> appliances;

    public static YamlRecipe createFromClassPath(String path) {
        final InputStream stream =
                YamlRecipe.class.getClassLoader().getResourceAsStream(path);
        Preconditions.checkNotNull(stream);
        return createFromStream(stream);
    }

    public static YamlRecipe createFromStream(InputStream stream) {
        final Yaml yaml = new Yaml();
        final Map<?, ?> map = (Map<?, ?>) yaml.load(stream);
        return new YamlRecipe(map);
    }

    public static YamlRecipe createFromString(String string) {
        final Yaml yaml = new Yaml();
        final Map map = (Map) yaml.load(string);
        return new YamlRecipe(map);
    }

    private YamlRecipe(Map<?, ?> yaml) {
        Preconditions.checkNotNull(yaml);
        createRecipe(yaml);
    }

    private void createRecipe(Map<?, ?> yaml) {
        for (Object entry : yaml.entrySet()) {
            final Map.Entry<?, ?> typedEntry = (Map.Entry<?, ?>) entry;
            if (typedEntry.getValue() instanceof Map<?, ?>) {
                final Map<?, ?> map = (Map<?, ?>) ((Map.Entry<?, ?>) entry).getValue();
                Preconditions.checkArgument(map.containsKey("type"));
                Preconditions.checkArgument(map.get("type") instanceof String);
                String type = (String) map.get("type");
                if (type.equals("appliance")) {
                    Appliance appliance = createAppliance(yaml, typedEntry.getKey().toString(), map);
                    if (appliances == null)
                        appliances = new HashMap<String, Appliance>();
                    appliances.put(typedEntry.getKey().toString(), appliance);
                }
            }
        }
    }

    private Appliance createAppliance(Map<?, ?> yaml, String name, Map<?, ?> props) {
        final Appliance.Builder builder = new Appliance.Builder().name(name);
        if (props.containsKey("workflows")) {
            Preconditions.checkArgument(props.get("workflows") instanceof List<?>);
            builder.workflows(toStringList((List<?>) props.get("workflows")));
        }
        if (props.containsKey("resources")) {
            Preconditions.checkArgument(props.get("resources") instanceof List<?>);
            final Map<String, Resource> resources = Maps.newHashMap();
            for (String resourceName : toStringList((List<?>) props.get("resources"))) {
                Preconditions.checkArgument(yaml.containsKey(resourceName));
                Resource resource = createResource(resourceName, (Map<?, ?>) yaml.get(resourceName));
                resources.put(resourceName, resource);
            }
            builder.resources(resources);
        }
        return builder.build();
    }

    private List<String> toStringList(List<?> workflows) {
        return Lists.transform(workflows, new Function<Object, String>() {
            @Override
            public String apply(Object item) {
                Preconditions.checkNotNull(item);
                return item.toString();
            }
        });
    }

    private Resource createResource(String name, Map<?, ?> map) {
        Preconditions.checkArgument(map.containsKey("type"));
        Preconditions.checkArgument(map.get("type") instanceof String);
        final String type = (String) map.get("type");
        Preconditions.checkArgument(type.equals("resource"));
        Map<String, String> config;
        if (map.containsKey("config")) {
            Preconditions.checkArgument(map.get("config") instanceof Map);
            config = toStringsMap((Map<?, ?>) map.get("config"));
        } else {
            config = Maps.newHashMap();
        }
        return new Resource.Builder().name(name).config(config).build();
    }

    private Map<String, String> toStringsMap(Map<?, ?> map) {
        final Map<String, String> stringsMap = Maps.newHashMap();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            stringsMap.put(entry.getKey().toString(), entry.getValue().toString());
        }
        return stringsMap;
    }

    @Override
    public Map<String, Appliance> getAppliances() {
        return appliances;
    }

    // TODO: create a an interface with a toMap() method which is also relevant for Resource & Appliance.
    public Map<String, Object> toMap() {
        final Map<String, Object> map = Maps.newHashMap();
        final Map<String, Object> appliances = Maps.newHashMap();
        for (Map.Entry<String, Appliance> entry : getAppliances().entrySet()) {
            appliances.put(entry.getKey(), entry.getValue().toMap());
        }
        map.put("appliances", appliances);
        return map;
    }
}
