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

import com.fasterxml.jackson.annotation.JsonUnwrapped;

/**
 * The placement of instances on agents for a specific service. Sent from planner to orchestrator.
 * TODO: Merge this class with {@link ServiceConfig}
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceDeploymentPlan {

    private ServiceConfig serviceConfig;
    private boolean autoUninstall;

    public ServiceDeploymentPlan() {

    }

    @JsonUnwrapped
    public ServiceConfig getServiceConfig() {
        return serviceConfig;
    }

    public void setServiceConfig(ServiceConfig service) {
        this.serviceConfig = service;
    }

    public void setAutoUninstall(boolean autoUninstall) {
        this.autoUninstall = autoUninstall;
    }

    public boolean isAutoUninstall() {
        return autoUninstall;
    }
}

