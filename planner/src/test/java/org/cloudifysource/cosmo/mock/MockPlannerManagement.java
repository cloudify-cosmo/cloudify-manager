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
package org.cloudifysource.cosmo.mock;

import org.cloudifysource.cosmo.service.ServiceGridCapacityPlanner;
import org.cloudifysource.cosmo.service.ServiceGridCapacityPlannerParameter;
import org.cloudifysource.cosmo.service.ServiceGridDeploymentPlanner;
import org.cloudifysource.cosmo.service.ServiceGridDeploymentPlannerParameter;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;

/**
 * Mock for management node that includes deployment and capacity planner.
 * @author itaif
 * @since 0.1
 */
public class MockPlannerManagement extends MockManagement {

    private final URI deploymentPlannerId;
    private final URI capacityPlannerId;

    public MockPlannerManagement() {
        super();
        deploymentPlannerId = super.createUri("services/deployment_planner/");
        capacityPlannerId = super.createUri("services/capacity_planner/");
    }

    public URI getDeploymentPlannerId() {
        return deploymentPlannerId;
    }

    @Override
    public void unregisterTaskConsumers() {
        super.unregisterTaskConsumers();
        super.unregisterTaskConsumer(deploymentPlannerId);
        super.unregisterTaskConsumer(capacityPlannerId);
    }

    @Override
    protected void registerTaskConsumers() {
        super.registerTaskConsumers();
        registerTaskConsumer(newServiceGridDeploymentPlanner(super.getTimeProvider()), deploymentPlannerId);
        registerTaskConsumer(newServiceGridCapacityPlanner(super.getTimeProvider()), capacityPlannerId);
    }


    private ServiceGridDeploymentPlanner newServiceGridDeploymentPlanner(CurrentTimeProvider timeProvider) {

        final ServiceGridDeploymentPlannerParameter deploymentPlannerParameter =
                new ServiceGridDeploymentPlannerParameter();
        deploymentPlannerParameter.setOrchestratorId(getOrchestratorId());
        deploymentPlannerParameter.setDeploymentPlannerId(getDeploymentPlannerId());
        return new ServiceGridDeploymentPlanner(deploymentPlannerParameter);
    }

    private ServiceGridCapacityPlanner newServiceGridCapacityPlanner(CurrentTimeProvider timeProvider) {

        final ServiceGridCapacityPlannerParameter capacityPlannerParameter = new ServiceGridCapacityPlannerParameter();
        capacityPlannerParameter.setDeploymentPlannerId(deploymentPlannerId);
        capacityPlannerParameter.setTaskReader(getTaskReader());
        capacityPlannerParameter.setStateReader(getStateReader());
        capacityPlannerParameter.setCapacityPlannerId(capacityPlannerId);
        return new ServiceGridCapacityPlanner(capacityPlannerParameter);
    }

    public URI getCapacityPlannerId() {
        return capacityPlannerId;
    }
}
