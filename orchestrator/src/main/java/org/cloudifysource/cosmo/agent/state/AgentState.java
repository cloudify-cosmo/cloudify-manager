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
package org.cloudifysource.cosmo.agent.state;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Preconditions;
import org.cloudifysource.cosmo.TaskConsumerState;

import java.net.URI;
import java.util.List;

/**
 * State of the Agent TaskConsumer.
 * @author Itai Frenkel
 * @since 0.1
 */
public class AgentState extends TaskConsumerState {

    /**
     * Possible values for {@link AgentState#setProgress(String)}.
     */
    public static class Progress {
        public static final String PLANNED = "PLANNED";
        public static final String STARTING_MACHINE = "STARTING_MACHINE";
        public static final String MACHINE_STARTED = "MACHINE_STARTED";
        public static final String AGENT_STARTED = "AGENT_STARTED";
        public static final String MACHINE_MARKED_FOR_TERMINATION = "MACHINE_MARKED_FOR_TERMINATION";
        public static final String TERMINATING_MACHINE = "TERMINATING_MACHINE";
        public static final String MACHINE_TERMINATED = "MACHINE_TERMINATED";
    }

    private String progress;
    private String ipAddress;
    private List<URI> serviceInstanceIds;
    private int numberOfAgentRestarts;
    private int numberOfMachineRestarts;
    private long lastPingSourceTimestamp;

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

    public void setProgress(String progress) {
        this.progress = progress;
    }

    public void setIpAddress(String ipAddress) {
        this.ipAddress = ipAddress;
    }

    public String getIpAddress() {
        return ipAddress;
    }

    public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
        this.serviceInstanceIds = serviceInstanceIds;
    }

    public List<URI> getServiceInstanceIds() {
        return serviceInstanceIds;
    }

    public int getNumberOfAgentRestarts() {
        return numberOfAgentRestarts;
    }

    public void setNumberOfAgentRestarts(int numberOfAgentRestarts) {
        this.numberOfAgentRestarts = numberOfAgentRestarts;
    }

    public int getNumberOfMachineRestarts() {
        return numberOfMachineRestarts;
    }

    public void setNumberOfMachineRestarts(int numberOfMachineRestarts) {
        this.numberOfMachineRestarts = numberOfMachineRestarts;
    }

    @JsonIgnore
    public void removeServiceInstanceId(final URI instanceId) {
        boolean removed = serviceInstanceIds.remove(instanceId);
        Preconditions.checkArgument(removed, "Cannot remove instance %s", instanceId);
    }

    public long getLastPingSourceTimestamp() {
        return lastPingSourceTimestamp;
    }

    public void setLastPingSourceTimestamp(long lastPingSourceTimestamp) {
        this.lastPingSourceTimestamp = lastPingSourceTimestamp;
    }
}
