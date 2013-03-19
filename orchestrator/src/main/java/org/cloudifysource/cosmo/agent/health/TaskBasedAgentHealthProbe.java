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

package org.cloudifysource.cosmo.agent.health;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.base.Objects;
import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskProducer;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * An implementation of the {@link AgentHealthProbe} which checks the successful full path of sending a task to each
 * agent and checks that it has executed it successfully and updated its state accordingly.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public class TaskBasedAgentHealthProbe implements AgentHealthProbe {


    public static final long AGENT_UNREACHABLE_MILLISECONDS = TimeUnit.SECONDS.toMillis(30);

    private static final long AGENT_REACHABLE_RENEW_MILLISECONDS = AGENT_UNREACHABLE_MILLISECONDS / 2;

    private final TaskBasedAgentHealthProbeState state;

    private final CurrentTimeProvider timeProvider;
    private final StateReader stateReader;
    private final Random challengeGenerator;

    private Iterable<URI> monitoredAgentsIds = Sets.newLinkedHashSet();



    public TaskBasedAgentHealthProbe(CurrentTimeProvider timeProvider, StateReader stateReader) {
        this.timeProvider = timeProvider;
        this.stateReader = stateReader;
        this.state = new TaskBasedAgentHealthProbeState();
        this.challengeGenerator = new Random();
    }

    @TaskConsumerStateHolder
    public TaskBasedAgentHealthProbeState getState() {
        return state;
    }

    @Override
    public void monitorAgents(Iterable<URI> agentsIds) {
        this.monitoredAgentsIds = agentsIds;
    }

    @Override
    public boolean isAgentUnreachable(URI agentId, Optional<Object> agentGeneration) {
        if (!getProbeStateMap().containsKey(agentId)) {
            return false;
        }

        final ProbeState probeState = getProbeStateMap().get(agentId);
        boolean unreachable = probeState.isUnreachable();
        if (!unreachable) {
            return false;
        }

        if (!Objects.equal(agentGeneration.orNull(), probeState.getPingAgentGeneration())) {
            return false;
        }

        return true;
    }

    @Override
    public Optional<Long> getAgentUnreachablePeriod(URI agentId, Optional<Object> agentGeneration) {
        if (!getProbeStateMap().containsKey(agentId)) {
            return Optional.absent();
        }

        ProbeState probeState = getProbeStateMap().get(agentId);
        if (!probeState.isUnreachable()) {
            return Optional.absent();
        }

        if (!Objects.equal(agentGeneration.orNull(), probeState.getPingAgentGeneration())) {
            return Optional.absent();
        }

        return Optional.of(timeProvider.currentTimeMillis() - probeState.getUnreachableTimestamp());
    }


    @TaskProducer
    public Iterable<Task> orchestrate() {

        final List<Task> newTasks = Lists.newArrayList();

        pingAgents(newTasks);

        return newTasks;
    }

    /**
     * Ping all agents that are not doing anything.
     */
    private void pingAgents(List<Task> newTasks) {

        final long nowTimestamp = timeProvider.currentTimeMillis();

        final Iterable<URI> currentMonitoredAgentsIds = monitoredAgentsIds;
        final Map<URI, ProbeState> currentProbeMap = syncProbeStateMapWithMonitoredAgents(currentMonitoredAgentsIds);
        for (URI agentId : currentMonitoredAgentsIds) {
            if (shouldPing(agentId, currentProbeMap, nowTimestamp)) {
                sendPing(agentId, currentProbeMap, newTasks, nowTimestamp);
            } else {
                verifyState(agentId, currentProbeMap, nowTimestamp);
            }
        }
        setProbeStateMap(currentProbeMap);
    }

    private void verifyState(URI agentId, Map<URI, ProbeState> currentProbeMap, long nowTimestamp) {
        final ProbeState probeState = currentProbeMap.get(agentId);
        Preconditions.checkNotNull(probeState);

        final long timeSinceLastVerification = nowTimestamp - probeState.getLastVerificationTimestamp();
        if (!probeState.isUnreachable() && timeSinceLastVerification <= AGENT_REACHABLE_RENEW_MILLISECONDS) {
            return;
        }

        final Optional<AgentState> agentStateOptional = getAgentState(agentId);
        if (agentStateOptional.isPresent()) {
            final AgentState agentState = agentStateOptional.get();
            final Object challenge = agentState.getLastPingChallenge();
            if (Objects.equal(challenge, probeState.getChallenge())) {
                onAgentNotUnreachable(nowTimestamp, probeState);
            } else if (timeSinceLastVerification > AGENT_UNREACHABLE_MILLISECONDS) {
                onAgentUnreachable(probeState, nowTimestamp);
            }
        } else {
            onAgentUnreachable(probeState, nowTimestamp);
        }

    }

    private void onAgentNotUnreachable(long nowTimestamp, ProbeState probeState) {
        probeState.setLastVerificationTimestamp(nowTimestamp);
        probeState.setUnreachable(false);
    }

    private void onAgentUnreachable(ProbeState probeState, long nowTimestamp) {
        if (!probeState.isUnreachable()) {
            probeState.setUnreachable(true);
            probeState.setUnreachableTimestamp(nowTimestamp);
        }
    }

    private void sendPing(URI agentId, Map<URI, ProbeState> currentProbeMap,
                          List<Task> newTasks, long nowTimestamp) {
        final ProbeState probeState = currentProbeMap.get(agentId);
        Preconditions.checkNotNull(probeState);
        final PingAgentTask pingAgentTask = new PingAgentTask();
        final Object challenge = createChallenge();
        pingAgentTask.setConsumerId(agentId);
        pingAgentTask.setChallenge(challenge);
        probeState.setLastPingTimestamp(nowTimestamp);
        probeState.setChallenge(challenge);
        final Optional<AgentState> agentState = getAgentState(agentId);
        final Object agentGeneration = agentState.isPresent() ? agentState.get().getAgentGeneration() : null;
        if (!Objects.equal(agentGeneration, probeState.getPingAgentGeneration())) {
            probeState.setPingAgentGeneration(agentGeneration);
            onAgentNotUnreachable(nowTimestamp, probeState);
        }

        newTasks.add(pingAgentTask);
    }

    private Object createChallenge() {
        return challengeGenerator.nextLong();
    }

    private boolean shouldPing(URI agentId, Map<URI, ProbeState> currentProbeMap, long nowTimestamp) {
        final ProbeState probeState = currentProbeMap.get(agentId);
        Preconditions.checkNotNull(probeState);
        if (probeState.isUnreachable()) {
            if (nowTimestamp - probeState.getLastPingTimestamp() >
                    AGENT_REACHABLE_RENEW_MILLISECONDS) {
                return true;
            }
            return false;
        } else {
            //Should we use same timestamp? maybe it should be last verified time instead of ping time
            if (nowTimestamp - probeState.getLastPingTimestamp() >
                    AGENT_REACHABLE_RENEW_MILLISECONDS) {
                return true;
            }
            return false;
        }


    }

    private Map<URI, ProbeState> syncProbeStateMapWithMonitoredAgents(Iterable<URI> currentMonitoredAgentsIds) {
        final Map<URI, ProbeState> syncedProbeStateMap = Maps.newHashMap();
        for (URI monitoredAgentsId : currentMonitoredAgentsIds) {
            final ProbeState probeState = getProbeStateMap().containsKey(monitoredAgentsId) ? ProbeState
                    .clone(getProbeStateMap().get(monitoredAgentsId)) : new ProbeState();
            syncedProbeStateMap.put(monitoredAgentsId, probeState);
        }
        return syncedProbeStateMap;
    }

    private Optional<AgentState> getAgentState(URI agentId) {
        return Optional.fromNullable(ServiceUtils.getAgentState(stateReader, agentId));
    }

    public Map<URI, ProbeState> getProbeStateMap() {
        return state.getProbeStateMap();
    }

    public void setProbeStateMap(Map<URI, ProbeState> probeStateMap) {
        this.state.setProbeStateMap(probeStateMap);
    }

    /**
     * Internal probe state per monitored agent.
     */
    public static class ProbeState {
        private boolean unreachable;
        private long lastPingTimestamp;
        private Object challenge;
        private long lastVerificationTimestamp;
        private long unreachableTimestamp;
        private Object pingAgentGeneration;

        public boolean isUnreachable() {
            return unreachable;
        }

        public void setUnreachable(boolean unreachable) {
            this.unreachable = unreachable;
        }

        public long getLastPingTimestamp() {
            return lastPingTimestamp;
        }

        public void setLastPingTimestamp(long lastPingTimestamp) {
            this.lastPingTimestamp = lastPingTimestamp;
        }

        public void setChallenge(Object challenge) {
            this.challenge = challenge;
        }

        public Object getChallenge() {
            return challenge;
        }

        public long getLastVerificationTimestamp() {
            return lastVerificationTimestamp;
        }

        public void setLastVerificationTimestamp(long lastVerificationTimestamp) {
            this.lastVerificationTimestamp = lastVerificationTimestamp;
        }

        public long getUnreachableTimestamp() {
            return unreachableTimestamp;
        }

        public void setUnreachableTimestamp(long unreachableTimestamp) {
            this.unreachableTimestamp = unreachableTimestamp;
        }

        @JsonIgnore
        public static ProbeState clone(ProbeState probeState) {
            ProbeState clone = new ProbeState();
            clone.setLastPingTimestamp(probeState.getLastPingTimestamp());
            clone.setUnreachable(probeState.isUnreachable());
            clone.setUnreachableTimestamp(probeState.getUnreachableTimestamp());
            clone.setLastVerificationTimestamp(probeState.getLastVerificationTimestamp());
            clone.setChallenge(probeState.getChallenge());
            clone.setPingAgentGeneration(probeState.getPingAgentGeneration());
            return clone;
        }

        public void setPingAgentGeneration(Object pingAgentGeneration) {
            this.pingAgentGeneration = pingAgentGeneration;
        }

        public Object getPingAgentGeneration() {
            return pingAgentGeneration;
        }

    }
}
