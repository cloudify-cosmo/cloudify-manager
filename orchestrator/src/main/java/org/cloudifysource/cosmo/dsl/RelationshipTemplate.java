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

/**
 * Data container for a relationship template in a node template of the dsl.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class RelationshipTemplate {

    private String type;
    private String target;

    private String plugin;
    private String bindAt;
    private String runOnNode;

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public String getBindAt() {
        return bindAt;
    }

    public void setBindAt(String bindAt) {
        this.bindAt = bindAt;
    }

    public String getRunOnNode() {
        return runOnNode;
    }

    public void setRunOnNode(String runOnNode) {
        this.runOnNode = runOnNode;
    }

    public String getPlugin() {
        return plugin;
    }

    public void setPlugin(String plugin) {
        this.plugin = plugin;
    }
}
