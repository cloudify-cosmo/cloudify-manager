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

import org.testng.annotations.Test;

import java.util.Map;
import java.util.Set;

import static org.testng.Assert.assertEquals;
import static org.testng.Assert.assertNotNull;
import static org.testng.Assert.assertTrue;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class YamlRecipeTest {

    @Test
    public void testSimpleStringRecipe() {
        Recipe recipe = YamlRecipe.createFromString("test:\n  type: appliance");
        assertNotNull(recipe.getAppliances());
        assertTrue(recipe.getAppliances().containsKey("test"));
        Appliance appliance = recipe.getAppliances().get("test");
        assertEquals(appliance.getName(), "test");
    }

    @Test
    public void testRecipeFromClassPath() {
        YamlRecipe recipe = YamlRecipe.createFromClassPath("recipes/yaml/vm_appliance.yaml");
        assertNotNull(recipe);
        assertNotNull(recipe.getAppliances());
        assertTrue(recipe.getAppliances().containsKey("vm_appliance"));
        Appliance appliance = recipe.getAppliances().get("vm_appliance");
        assertEquals(appliance.getName(), "vm_appliance");
        Set<String> workflows = appliance.getWorkflows();
        assertNotNull(workflows);
        assertEquals(workflows.size(), 4);
        assertTrue(workflows.contains("start_appliance"));
        assertTrue(workflows.contains("monitor"));
        assertTrue(workflows.contains("unmonitor"));
        assertTrue(workflows.contains("run_script_on_vm"));
        Map<String, Resource> resources = appliance.getResources();
        assertNotNull(resources);
        assertEquals(resources.size(), 2);
        assertTrue(resources.containsKey("cosmo_agent"));
        assertTrue(resources.containsKey("tomcat"));
        Resource tomcat = resources.get("tomcat");
        assertEquals(tomcat.getName(), "tomcat");
        assertNotNull(tomcat.getConfig());
        assertTrue(tomcat.getConfig().containsKey("default_configurer"));
        assertEquals(tomcat.getConfig().get("default_configurer"), "chef");
        assertEquals(tomcat.getConfig().get("chef_recipe"), "tomcat.rb");
        Resource cosmoAgent = resources.get("cosmo_agent");
        assertEquals(cosmoAgent.getName(), "cosmo_agent");
        assertNotNull(cosmoAgent.getConfig());
        assertEquals(cosmoAgent.getConfig().size(), 0);
    }

}
