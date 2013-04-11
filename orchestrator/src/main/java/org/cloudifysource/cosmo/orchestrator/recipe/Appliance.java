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

import com.google.common.base.Preconditions;
import com.google.common.collect.Sets;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class Appliance {

    private final String name;
    private final Map<String, Resource> resources;
    private final Set<String> workflows;

    private Appliance(String name, List<String> workflows, Map<String, Resource> resources) {
        this.name = name;
        this.resources = resources;
        this.workflows = Sets.newHashSet(workflows);
    }

    public Set<String> getWorkflows() {
        return workflows;
    }

    public Map<String, Resource> getResources() {
        return resources;
    }

    public String getName() {
        return name;
    }

    public static class Builder {
        private String name;
        private List<String> workflows;
        private Map<String, Resource> resources;

        public Appliance build() {
            Preconditions.checkNotNull(name);
            return new Appliance(name, workflows != null ? workflows : Collections.<String>emptyList(),
                    resources != null ? resources : Collections.<String, Resource>emptyMap());
        }

        public Builder name(String name) {
            this.name = name;
            return this;
        }

        public Builder workflows(List<String> workflows) {
            this.workflows = workflows;
            return this;
        }

        public Builder resources(Map<String, Resource> resources) {
            this.resources = resources;
            return this;
        }
    }
}
