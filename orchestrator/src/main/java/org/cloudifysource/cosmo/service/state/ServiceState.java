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
import com.fasterxml.jackson.annotation.JsonUnwrapped;
import com.google.common.base.Preconditions;
import org.cloudifysource.cosmo.TaskConsumerState;

import java.net.URI;
import java.util.List;

/**
 * Describes the state of a service, as decided by the {@link org.cloudifysource.cosmo.service
 * .ServiceGridOrchestrator}.
 *
 * @see ServiceInstanceState
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceState extends TaskConsumerState {

    /**
     * Describes the service state machine {@link #setProgress(String)}.
     */
    public static class Progress {
        public static final String INSTALLING_SERVICE = "INSTALLING_SERVICE";
        public static final String SERVICE_INSTALLED = "SERVICE_INSTALLED";
        public static final String UNINSTALLING_SERVICE = "UNINSTALLING_SERVICE";
        public static final String SERVICE_UNINSTALLED = "SERVICE_UNINSTALLED";
    }

    private List<URI> instanceIds;
    private ServiceConfig serviceConfig;
    private String progress;

    public void setServiceConfig(ServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    @JsonUnwrapped
    public ServiceConfig getServiceConfig() {
        return serviceConfig;
    }

    public List<URI> getInstanceIds() {
        return instanceIds;
    }

    public void setInstanceIds(List<URI> instanceIds) {
        this.instanceIds = instanceIds;
    }

    public void setProgress(String progress) {
        this.progress = progress;
    }

    /**
     * Use isProgress(x or y or z) instead.
     * This is to encourage using the pattern of positive progress checks such as "isProgress(y)"
     * instead of negative progress checks such as (!getProgress().equals(x))
     */
    @Deprecated
    public String getProgress() {
        return progress;
    }

    /**
     * @return true if {@code #getProgress()} matches any of the specified options.
     */
    public boolean isProgress(String ... expectedProgresses) {
        for (String expectedProgress : expectedProgresses) {
            if (progress != null && progress.equals(expectedProgress)) {
                return true;
            }
        }
        return false;
    }

    @JsonIgnore
    public void removeInstance(URI instanceId) {
        boolean removed = instanceIds.remove(instanceId);
        Preconditions.checkArgument(removed, "Cannot remove instance %s", instanceId);
    }
}
