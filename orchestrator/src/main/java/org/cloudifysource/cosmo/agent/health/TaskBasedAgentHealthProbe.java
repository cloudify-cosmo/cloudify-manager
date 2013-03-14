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

import com.google.common.base.Preconditions;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.TaskConsumerStateHolder;
import org.cloudifysource.cosmo.TaskProducer;
import org.cloudifysource.cosmo.TaskReader;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.service.ServiceUtils;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.time.CurrentTimeProvider;

import java.net.URI;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * An implementation of the {@link AgentHealthProbe} which checks the successful full path of sending a task to each
 * agent and checks that it has executed it successfully and updated its state accordingly.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public class TaskBasedAgentHealthProbe implements AgentHealthProbe {


    private static final long AGENT_UNREACHABLE_MILLISECONDS = TimeUnit.SECONDS.toMillis(30);

    private static final long AGENT_REACHABLE_RENEW_MILLISECONDS = AGENT_UNREACHABLE_MILLISECONDS / 2;

    private final TaskBasedAgentHealthProbeState state;

    private final CurrentTimeProvider timeProvider;
    private final TaskReader taskReader;
    private final StateReader stateReader;
    private final URI agentProbeId;

    private Iterable<URI> monitoredAgentsIds = Sets.newLinkedHashSet();


    public TaskBasedAgentHealthProbe(CurrentTimeProvider timeProvider, TaskReader taskReader, StateReader stateReader,
                                     URI agentProbeId) {
        this.timeProvider = timeProvider;
        this.taskReader = taskReader;
        this.stateReader = stateReader;
        this.agentProbeId = agentProbeId;
        this.state = new TaskBasedAgentHealthProbeState();
    }

    @TaskConsumerStateHolder
    public TaskBasedAgentHealthProbeState getState() {
        return state;
    }

    private AgentPingHealth getAgentHealthStatus(URI agentId, long nowTimestamp) {
        AgentPingHealth health = AgentPingHealth.UNDETERMINED;

        // look for ping that should have been consumed by now --> AGENT_NOT_RESPONDING
        AgentState agentState = getAgentState(agentId);

        // look for ping that was consumed just recently --> AGENT_REACHABLE
        if (agentState != null) {
            final long taskTimestamp = agentState.getLastPingSourceTimestamp();
            final long sincePingMilliseconds = nowTimestamp - taskTimestamp;
            if (sincePingMilliseconds <= AGENT_UNREACHABLE_MILLISECONDS) {
                // ping was consumed just recently
                return  AgentPingHealth.AGENT_REACHABLE;
            }
        }

        if (health == AgentPingHealth.UNDETERMINED) {

            Iterable<Task> pendingTasks = taskReader.getPendingTasks(agentId);
            for (final Task task : pendingTasks) {
                if (task instanceof PingAgentTask) {
                    Preconditions.checkState(
                            task.getProducerId().equals(agentProbeId),
                            "All ping tasks are assumed to be from this agent probe");
                    PingAgentTask pingAgentTask = (PingAgentTask) task;
                    Integer expectedNumberOfAgentRestartsInAgentState =
                            pingAgentTask.getExpectedNumberOfAgentRestartsInAgentState();
                    Integer expectedNumberOfMachineRestartsInAgentState =
                            pingAgentTask.getExpectedNumberOfMachineRestartsInAgentState();
                    if (expectedNumberOfAgentRestartsInAgentState == null && agentState != null) {
                        Preconditions.checkState(expectedNumberOfMachineRestartsInAgentState == null);
                        if (agentState.isMachineReachableLifecycle()) {
                            // agent started after ping sent. Wait for next ping
                        } else {
                            // agent not reachable because it was not started yet
                            health = AgentPingHealth.AGENT_UNREACHABLE;
                        }
                    } else if (expectedNumberOfMachineRestartsInAgentState != null &&
                               agentState != null &&
                               expectedNumberOfMachineRestartsInAgentState != agentState.getNumberOfMachineStarts()) {
                        Preconditions.checkState(
                                expectedNumberOfMachineRestartsInAgentState < agentState.getNumberOfMachineStarts(),
                                "Could not have sent ping to a machine that was not restarted yet");
                        // machine restarted after ping sent. Wait for next ping
                    } else if (expectedNumberOfAgentRestartsInAgentState != null &&
                               agentState != null &&
                               expectedNumberOfAgentRestartsInAgentState != agentState.getNumberOfAgentStarts()) {
                        Preconditions.checkState(
                                expectedNumberOfAgentRestartsInAgentState < agentState.getNumberOfAgentStarts(),
                                "Could not have sent ping to an agent that was not restarted yet");
                        // agent restarted after ping sent. Wait for next ping
                    } else {
                        final long taskTimestamp = task.getProducerTimestamp();
                        final long notRespondingMilliseconds = nowTimestamp - taskTimestamp;
                        if (notRespondingMilliseconds > AGENT_UNREACHABLE_MILLISECONDS) {
                            // ping should have been consumed by now
                            health = AgentPingHealth.AGENT_UNREACHABLE;
                        }
                    }
                }
            }
        }

        return health;
    }

    @Override
    public Map<URI, Boolean> getAgentsHealthStatus() {
        final Map<URI, Boolean> result = Maps.newHashMap();
        final long nowTimestamp = timeProvider.currentTimeMillis();
        for (URI monitoredAgentsId : monitoredAgentsIds) {
            AgentPingHealth agentHealthStatus = getAgentHealthStatus(monitoredAgentsId, nowTimestamp);
            result.put(monitoredAgentsId, agentHealthStatus == AgentPingHealth.AGENT_UNREACHABLE);
        }
        return result;
    }

    @Override
    public void monitorAgents(Iterable<URI> agentsIds) {
        this.monitoredAgentsIds = agentsIds;
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

        long nowTimestamp = timeProvider.currentTimeMillis();
        for (final URI agentId : monitoredAgentsIds) {

            final AgentState agentState = getAgentState(agentId);

            AgentPingHealth agentPingHealth = getAgentHealthStatus(agentId, nowTimestamp);
            if (agentPingHealth.equals(AgentPingHealth.AGENT_REACHABLE)) {
                final long taskTimestamp = agentState.getLastPingSourceTimestamp();
                final long sincePingMilliseconds = nowTimestamp - taskTimestamp;
                if (sincePingMilliseconds < AGENT_REACHABLE_RENEW_MILLISECONDS) {
                    continue;
                }
            }

            final PingAgentTask pingTask = new PingAgentTask();
            pingTask.setConsumerId(agentId);
            if (agentState != null && agentState.isMachineReachableLifecycle()) {

                pingTask.setExpectedNumberOfAgentRestartsInAgentState(agentState.getNumberOfAgentStarts());
                pingTask.setExpectedNumberOfMachineRestartsInAgentState(agentState.getNumberOfMachineStarts());
            }
            addNewTaskIfNotExists(newTasks, pingTask);
        }

    }

    private AgentState getAgentState(URI agentId) {
        return ServiceUtils.getAgentState(stateReader, agentId);
    }

    private boolean isAgentProgress(AgentState agentState,
                                    String ... expectedProgresses) {
        if (agentState == null) {
            return false;
        }

        for (String progress : expectedProgresses) {
            if (agentState.getStateMachine().isLifecycleState(new LifecycleState(progress))) {
                return true;
            }
        }

        return false;
    }

    /**
     * Adds a new task only if it has not been added recently.
     */
    public void addNewTaskIfNotExists(
            final List<Task> newTasks,
            final Task newTask) {

        addNewTask(newTasks, newTask);
    }

    private static void addNewTask(List<Task> newTasks, final Task task) {
        newTasks.add(task);
    }
}
