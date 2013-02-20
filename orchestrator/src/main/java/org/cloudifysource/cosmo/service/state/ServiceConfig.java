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
package org.cloudifysource.cosmo.service.state;

import java.net.URI;

/**
 * The basic information the service requires.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceConfig {

    private String displayName;
    private int plannedNumberOfInstances;
    private int maxNumberOfInstances;
    private int minNumberOfInstances;
    private URI id;

    public void setDisplayName(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setPlannedNumberOfInstances(int numberOfInstances) {
        this.plannedNumberOfInstances = numberOfInstances;
    }

    public int getPlannedNumberOfInstances() {
        return plannedNumberOfInstances;
    }

    public URI getServiceId() {
        return id;
    }

    public void setServiceId(URI id) {
        this.id = id;
    }

    public int getMaxNumberOfInstances() {
        return maxNumberOfInstances;
    }

    public void setMaxNumberOfInstances(int maxNumberOfInstances) {
        this.maxNumberOfInstances = maxNumberOfInstances;
    }

    public int getMinNumberOfInstances() {
        return minNumberOfInstances;
    }

    public void setMinNumberOfInstances(int minNumberOfInstances) {
        this.minNumberOfInstances = minNumberOfInstances;
    }

}
