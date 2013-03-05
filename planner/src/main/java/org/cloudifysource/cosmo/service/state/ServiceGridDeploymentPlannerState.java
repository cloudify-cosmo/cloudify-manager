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

import com.fasterxml.jackson.annotation.JsonIgnore;
import org.cloudifysource.cosmo.TaskConsumerState;

import java.net.URI;

/**
 * Represents the state of {@link org.cloudifysource.cosmo.service.ServiceGridDeploymentPlanner}.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridDeploymentPlannerState extends TaskConsumerState {

    private ServiceGridCapacityPlan capacityPlan;
    private boolean planChanged;

    public ServiceGridDeploymentPlannerState() {
        capacityPlan = new ServiceGridCapacityPlan();
    }

    public ServiceGridCapacityPlan getCapacityPlan() {
        return capacityPlan;
    }

    public void setCapacityPlan(ServiceGridCapacityPlan services) {
        this.capacityPlan = services;
    }

    @JsonIgnore
    public void addService(ServiceConfig serviceConfig) {
        capacityPlan.addService(serviceConfig);
    }

    @JsonIgnore
    public void removeService(final URI serviceId) {
        capacityPlan.removeServiceById(serviceId);
    }

    public void setOrchestratorUpdateRequired(boolean deploymentPlanningRequired) {
        this.planChanged = deploymentPlanningRequired;
    }

    public boolean isOrchestratorUpdateRequired() {
        return planChanged;
    }

    @JsonIgnore
    public void updateService(ServiceConfig serviceConfig) {
        setOrchestratorUpdateRequired(true);
    }

    public ServiceConfig getServiceById(final URI serviceId) {
        return capacityPlan.getServiceById(serviceId);
    }
}
