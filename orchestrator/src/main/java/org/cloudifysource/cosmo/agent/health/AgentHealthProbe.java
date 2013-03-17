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

import com.google.common.base.Optional;

import java.net.URI;

/**
 * Acts as a health probe for agents.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public interface AgentHealthProbe {

    /**
     * Specify which agents needs to be monitored for health status.
     * @param agentsIds the list of agents ids to monitor
     */
    void monitorAgents(Iterable<URI> agentsIds);

    /**
     * @param agentId the id of the agent which is checked for unreachability
     * @return true if the agent is considered unreachable
     */
    boolean isAgentUnreachable(URI agentId);

    /**
     * @param agentId the id of the agent which is checked for unreachability period
     * @return the period of time an agent is considered unreachable, will return an absent
     * optional if the given agent is not considered unreachable
     */
    Optional<Long> getAgentUnreachablePeriod(URI agentId);
}
