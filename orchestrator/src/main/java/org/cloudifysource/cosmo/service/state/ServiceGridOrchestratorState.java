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
import com.google.common.base.Preconditions;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.TaskConsumerState;

import java.net.URI;
import java.util.Set;

/**
 * The state object of {@link org.cloudifysource.cosmo.service.ServiceGridOrchestrator}.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceGridOrchestratorState extends TaskConsumerState {

    private ServiceGridDeploymentPlan deploymentPlan;
    private boolean syncedStateWithDeploymentBefore;
    private Set<URI> serviceIdsToUninstall = Sets.newHashSet();
    private URI serverId;

    public ServiceGridOrchestratorState() {
        deploymentPlan = new ServiceGridDeploymentPlan();
    }

    public void setServerId(URI serverId) {
        this.serverId = serverId;
    }

    public ServiceGridDeploymentPlan getDeploymentPlan() {
        return deploymentPlan;
    }

    public void setDeploymentPlan(ServiceGridDeploymentPlan deploymentPlan) {
        this.deploymentPlan = deploymentPlan;
    }

    public boolean isSyncedStateWithDeploymentBefore() {
        return syncedStateWithDeploymentBefore;
    }

    public void setSyncedStateWithDeploymentBefore(boolean firstSyncStateWithDeployment) {
        this.syncedStateWithDeploymentBefore = firstSyncStateWithDeployment;
    }

    @JsonIgnore
    public void addServiceIdToUninstall(URI serviceId) {
        this.serviceIdsToUninstall.add(serviceId);
    }

    @JsonIgnore
    public void removeServiceIdToUninstall(URI serviceId) {
        boolean removed = serviceIdsToUninstall.remove(serviceId);
        Preconditions.checkArgument(removed, "Cannot remove %s from services to uninstall list", serviceId);
    }

    public Set<URI> getServiceIdsToUninstall() {
        return serviceIdsToUninstall;
    }

    public void setServiceIdsToUninstall(Set<URI> serviceIds) {
        this.serviceIdsToUninstall = serviceIds;
    }

    public URI getServerId() {
        return serverId;
    }
}
