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

import java.util.Map;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class Resource {

    private final String name;
    private final Map<String, String> config;

    public Resource(String name, Map<String, String> config) {
        this.name = name;
        this.config = config;
    }

    public String getName() {
        return name;
    }

    public Map<String, String> getConfig() {
        return config;
    }

    public static class Builder {

        private String name;
        private Map<String, String> config;

        public Builder name(String name) {
            this.name = name;
            return this;
        }

        public Builder config(Map<String, String> config) {
            this.config = config;
            return this;
        }

        public Resource build() {
            Preconditions.checkNotNull(name);
            Preconditions.checkNotNull(config);
            return new Resource(name, config);
        }
    }

}
