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

    private String interfaceImplementation;
    private String runPhase;
    private String runLocation;

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

    public String getRunPhase() {
        return runPhase;
    }

    public void setRunPhase(String runPhase) {
        this.runPhase = runPhase;
    }

    public String getRunLocation() {
        return runLocation;
    }

    public void setRunLocation(String runLocation) {
        this.runLocation = runLocation;
    }

    public String getInterfaceImplementation() {
        return interfaceImplementation;
    }

    public void setInterfaceImplementation(String interfaceImplementation) {
        this.interfaceImplementation = interfaceImplementation;
    }
}
