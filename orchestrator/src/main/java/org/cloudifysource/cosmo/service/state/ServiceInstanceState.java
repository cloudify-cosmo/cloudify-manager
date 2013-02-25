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

import org.cloudifysource.cosmo.TaskConsumerState;

import java.net.URI;

/**
 * Descibes the state of a single service instance.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceInstanceState extends TaskConsumerState {

    private String lifecycle;
    private URI agentId;
    private URI serviceId;

    public void setLifecycle(String lifecycle) {
        this.lifecycle = lifecycle;
    }

    public URI getAgentId() {
        return agentId;
    }

    public void setAgentId(URI agentId) {
        this.agentId = agentId;
    }

    public URI getServiceId() {
        return serviceId;
    }

    public void setServiceId(URI serviceId) {
        this.serviceId = serviceId;
    }

    /**
     * @return instance lifecycle state.
     */
    public String getLifecycle() {
        return lifecycle;
    }

    /**
     * @return true if {@code #getLifecycle()} matches any of the specified options.
     */
    public boolean isLifecycle(String... expectedProgresses) {
        for (String expectedProgress : expectedProgresses) {
            if (lifecycle != null && lifecycle.equals(expectedProgress)) {
                return true;
            }
        }
        return false;
    }
}
