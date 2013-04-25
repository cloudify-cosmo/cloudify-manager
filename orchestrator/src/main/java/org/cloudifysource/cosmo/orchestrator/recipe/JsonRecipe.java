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

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class JsonRecipe {

    private final List<Map<String, Object>> list;

    public static JsonRecipe load(String recipe) throws IOException {
        ObjectMapper mapper = new ObjectMapper();
        final List<Map<String, Object>> list = mapper.readValue(recipe, new TypeReference<List<Map<String,
                Object>>>() {
        });
        return new JsonRecipe(list);
    }

    private JsonRecipe(List<Map<String, Object>> list) {
        this.list = list;
    }

    public Optional<Map<String, Object>> get(String name) {
        for (Map<String, Object> map : list) {
            if (name.equals(map.get("name")))
                return Optional.of(map);
        }
        return Optional.absent();
    }
}
