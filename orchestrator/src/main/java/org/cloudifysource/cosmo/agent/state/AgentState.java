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
import com.google.common.collect.Lists;
import org.cloudifysource.cosmo.TaskConsumerState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachineText;

import java.net.URI;
import java.util.List;

/**
 * State of the Agent TaskConsumer.
 * @author Itai Frenkel
 * @since 0.1
 */
public class AgentState extends TaskConsumerState {

    private static final String MACHINE_UNREACHABLE = "cloudmachine_unreachable";
    private static final String MACHINE_TERMINATED = "cloudmachine_terminated";
    private static final String MACHINE_REACHABLE = "cloudmachine_reachable";
    private static final String MACHINE_STARTED = "cloudmachine_started";

    public AgentState() {
        stateMachine = new LifecycleStateMachine();
        stateMachine.setLifecycleName(new LifecycleName("cloudmachine"));
        stateMachine.setText(new LifecycleStateMachineText(
                MACHINE_UNREACHABLE + "->" + MACHINE_TERMINATED + "<->" + MACHINE_STARTED + "->" +
                MACHINE_REACHABLE + "->" + MACHINE_TERMINATED));
        stateMachine.setBeginState(new LifecycleState(MACHINE_TERMINATED));
        stateMachine.setEndState(new LifecycleState(MACHINE_REACHABLE));
        serviceInstanceIds = Lists.newArrayList();
    }

    private LifecycleStateMachine stateMachine;
    private List<URI> serviceInstanceIds;
    private int numberOfAgentStarts;
    private int numberOfMachineStarts;
    private long lastPingSourceTimestamp;
    private String host;
    private String keyFile;
    private String userName;

    public void setServiceInstanceIds(List<URI> serviceInstanceIds) {
        this.serviceInstanceIds = serviceInstanceIds;
    }

    public List<URI> getServiceInstanceIds() {
        return serviceInstanceIds;
    }

    public int getNumberOfAgentStarts() {
        return numberOfAgentStarts;
    }

    public void setNumberOfAgentStarts(int numberOfAgentStarts) {
        this.numberOfAgentStarts = numberOfAgentStarts;
    }

    public int getNumberOfMachineStarts() {
        return numberOfMachineStarts;
    }

    public void setNumberOfMachineStarts(int numberOfMachineStarts) {
        this.numberOfMachineStarts = numberOfMachineStarts;
    }

    @JsonIgnore
    public boolean removeServiceInstanceId(final URI instanceId) {
        return serviceInstanceIds.remove(instanceId);
    }

    public long getLastPingSourceTimestamp() {
        return lastPingSourceTimestamp;
    }

    public void setLastPingSourceTimestamp(long lastPingSourceTimestamp) {
        this.lastPingSourceTimestamp = lastPingSourceTimestamp;
    }

    @JsonIgnore
    public void incrementNumberOfMachineStarts() {
        numberOfMachineStarts++;
    }

    @JsonIgnore
    public void incrementNumberOfAgentStarts() {
        numberOfAgentStarts++;
    }

    @JsonIgnore
    public void resetNumberOfAgentStarts() {
        numberOfAgentStarts = 0;
    }

    @JsonIgnore
    public LifecycleState getMachineTerminatedLifecycle() {
        return new LifecycleState(MACHINE_TERMINATED);
    }

    @JsonIgnore
    public LifecycleState getMachineReachableLifecycle() {
        return new LifecycleState(MACHINE_REACHABLE);
    }

    @JsonIgnore
    public LifecycleState getMachineStartedLifecycle() {
        return new LifecycleState(MACHINE_STARTED);
    }

    @JsonIgnore
    public boolean isMachineTerminatedLifecycle() {
        return  stateMachine.isLifecycleState(getMachineTerminatedLifecycle());
    }

    @JsonIgnore
    public boolean isMachineReachableLifecycle() {
        return  stateMachine.isLifecycleState(getMachineReachableLifecycle());
    }

    @JsonIgnore
    public LifecycleState getMachineUnreachableLifecycle() {
        return new LifecycleState(MACHINE_UNREACHABLE);
    }

    public LifecycleStateMachine getStateMachine() {
        return stateMachine;
    }

    public void setStateMachine(LifecycleStateMachine stateMachine) {
        this.stateMachine = stateMachine;
    }

    @JsonIgnore
    public boolean isMachineStartedLifecycle() {
        return  stateMachine.isLifecycleState(getMachineStartedLifecycle());
    }

    public boolean isMachineUnreachableLifecycle() {
        return  stateMachine.isLifecycleState(getMachineUnreachableLifecycle());
    }

    public void addServiceInstance(URI instanceId) {
        Preconditions.checkArgument(!serviceInstanceIds.contains(instanceId));
        serviceInstanceIds.add(instanceId);
    }

    public String getHost() {
        return host;
    }

    public void setHost(String host) {
        this.host = host;
    }

    public void setUserName(String userName) {
        this.userName = userName;
    }

    public String getUserName() {
        return userName;
    }

    public void setKeyFile(String keyFile) {
        this.keyFile = keyFile;
    }

    public String getKeyFile() {
        return keyFile;
    }

}
