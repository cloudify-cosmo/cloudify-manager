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
import com.google.common.collect.Iterables;
import org.cloudifysource.cosmo.TaskConsumerState;
import org.cloudifysource.cosmo.agent.state.AgentState;

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

    private List<URI> instanceIds;
    private ServiceConfig serviceConfig;
    private String progress;

    /**
     * Describes the service state machine {@link #setProgress(String)}.
     */
    public static class Progress {
        public static final String INSTALLING_SERVICE = "INSTALLING_SERVICE";
        public static final String SERVICE_INSTALLED = "SERVICE_INSTALLED";
        public static final String UNINSTALLING_SERVICE = "UNINSTALLING_SERVICE";
        public static final String SERVICE_UNINSTALLED = "SERVICE_UNINSTALLED";
    }

    /**
     * @return the initial state of the lifecycle state machine.
     */
    public String getInitialLifecycle() {
        return getServiceConfig().getInstanceLifecycleStateMachine().get(0);
    }


    public String getFinalInstanceLifecycle() {
        return Iterables.getLast(getServiceConfig().getInstanceLifecycleStateMachine());
    }

    /**
     * @param lifecycle - the current lifecycle
     * @return - the next lifecycle state
     *           or the specified lifecycle if this is the last lifecycle,
     *           or null if the specified lifecycle is not part of the state machine.
     */
    @JsonIgnore
    public String getNextInstanceLifecycle(String lifecycle) {
        if (lifecycle.equals(AgentState.Progress.AGENT_STARTED)) {
            return getInitialLifecycle();
        }
        int index = toInstanceLifecycleIndex(lifecycle);
        if (index < 0) {
            return null;
        }

        final int lastIndex = getServiceConfig().getInstanceLifecycleStateMachine().size() - 1;
        if (index  < lastIndex) {
            index++;
        }
        return getServiceConfig().getInstanceLifecycleStateMachine().get(index);
    }

    /**
     * @param lifecycle - the current instance lifecycle
     * @return - the prev lifecycle
     *           or lifecycle if there is no previous lifecycle,
     *           or null if the specified lifecycle is not part of the state machine
     */
    @JsonIgnore
    public String getPrevInstanceLifecycle(String lifecycle) {
        if (lifecycle.equals(AgentState.Progress.MACHINE_UNREACHABLE)) {
            return lifecycle;
        }

        int index = toInstanceLifecycleIndex(lifecycle);
        if (index < 0) {
            return null;
        }

        if (index == 0) {
            return lifecycle;
        }

        return getServiceConfig().getInstanceLifecycleStateMachine().get(index - 1);
    }

    private int toInstanceLifecycleIndex(String lifecycle) {
        Preconditions.checkNotNull(lifecycle);
        return this.getServiceConfig().getInstanceLifecycleStateMachine().indexOf(lifecycle);
    }

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
     * Use isLifecycle(x or y or z) instead.
     * This is to encourage using the pattern of positive progress checks such as "isLifecycle(y)"
     * instead of negative progress checks such as (!getLifecycle().equals(x))
     */
    @Deprecated
    public String getProgress() {
        return progress;
    }

    /**
     * @return true if {@code #getLifecycle()} matches any of the specified options.
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
