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
package org.cloudifysource.cosmo.orchestrator.recipe.json;

import com.google.common.base.Charsets;
import com.google.common.base.Optional;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.orchestrator.recipe.JsonRecipe;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.Test;

import java.io.IOException;
import java.net.URL;
import java.util.List;
import java.util.Map;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests JSON recipes parsing and object model.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class JsonRecipeTest {

    private JsonRecipe recipe;

    @BeforeClass
    public void loadRecipe() throws IOException {
        URL url = Resources.getResource("recipes/json/tomcat/tomcat_node_recipe.json");
        String json = Resources.toString(url, Charsets.UTF_8);
        recipe = JsonRecipe.load(json);
    }

    @Test
    public void testComponentsParsing() throws IOException {
        assertThat(recipe).isNotNull();
        // tomcat_node
        Optional<Map<String, Object>> tomcatNode = recipe.get("tomcat_node");
        assertThat(tomcatNode.isPresent()).isTrue();
        assertThat(tomcatNode.get()).isInstanceOf(Map.class);
        assertThat(tomcatNode.get().get("type")).isEqualTo("vm_node");
        // vm_node
        Optional<Map<String, Object>> vmNode = recipe.get("vm_node");
        assertThat(vmNode.isPresent()).isTrue();
        assertThat(vmNode.get()).isInstanceOf(Map.class);
        assertThat(vmNode.get().get("type")).isEqualTo("node");
        // tomcat
        Optional<Map<String, Object>> tomcat = recipe.get("tomcat");
        assertThat(tomcat.isPresent()).isTrue();
        assertThat(tomcat.get()).isInstanceOf(Map.class);
        assertThat(tomcat.get().get("type")).isEqualTo("resource");
        // vm
        Optional<Map<String, Object>> vm = recipe.get("vm");
        assertThat(vm.isPresent()).isTrue();
        assertThat(vm.get()).isInstanceOf(Map.class);
        assertThat(vm.get().get("type")).isEqualTo("resource");
    }

    @Test
    public void testGetResources() {
        Map<String, Object> tomcatNode = recipe.get("tomcat_node").get();
        Object resources = tomcatNode.get("resources");
        assertThat(resources).isInstanceOf(List.class);
        List<?> resourcesList = (List<?>) resources;
        assertThat(resourcesList.size()).isEqualTo(2);
        int i = 0;
        for (Object resource : resourcesList) {
            assertThat(resource).isInstanceOf(Map.class);
            Map<?, ?> resourceMap = (Map<?, ?>) resource;
            if (i == 0) {
                assertThat(resourceMap.get("name").toString()).isEqualTo("vm");
                assertThat(resourceMap.get("id").toString()).isEqualTo("vm");
            } else {
                assertThat(resourceMap.get("name").toString()).isEqualTo("tomcat");
                assertThat(resourceMap.get("id").toString()).isEqualTo("tomcat");
            }
            i++;
        }
    }

    @Test
    public void testGetNodes() {
        final List<String> nodes = recipe.getNodes();
        assertThat(nodes).isNotNull();
        assertThat(nodes.size()).isEqualTo(2);
        assertThat(nodes).contains("tomcat_node", "vm_node");
    }

}
