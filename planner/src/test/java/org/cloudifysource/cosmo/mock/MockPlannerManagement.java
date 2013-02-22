package org.cloudifysource.cosmo.mock;

import org.cloudifysource.cosmo.service.ServiceGridCapacityPlanner;
import org.cloudifysource.cosmo.service.ServiceGridCapacityPlannerParameter;
import org.cloudifysource.cosmo.service.ServiceGridDeploymentPlanner;
import org.cloudifysource.cosmo.service.ServiceGridDeploymentPlannerParameter;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;

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

        final ServiceGridDeploymentPlannerParameter deploymentPlannerParameter = new ServiceGridDeploymentPlannerParameter();
        deploymentPlannerParameter.setOrchestratorId(getOrchestratorId());
        deploymentPlannerParameter.setAgentsId(getAgentsId());
        deploymentPlannerParameter.setDeploymentPlannerId(deploymentPlannerId);
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
