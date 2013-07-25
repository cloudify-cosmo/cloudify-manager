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
 * Represents a
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class Policy {

    private Map<String, Rule> rules;
    private Map<String, Object> onEvent;

    public Map<String, Object> getOnEvent() {
        return onEvent;
    }

    public void setOnEvent(Map<String, Object> onEvent) {
        this.onEvent = onEvent;
    }

    public Map<String, Rule> getRules() {
        return rules;
    }

    public void setRules(Map<String, Rule> rules) {
        this.rules = rules;
    }
}
