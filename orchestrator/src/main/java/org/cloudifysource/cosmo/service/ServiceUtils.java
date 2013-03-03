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
package org.cloudifysource.cosmo.service;

import com.google.common.base.Preconditions;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.state.ServiceState;
import org.cloudifysource.cosmo.state.EtagState;
import org.cloudifysource.cosmo.state.StateReader;
import org.cloudifysource.cosmo.streams.StreamUtils;

import java.net.URI;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A temporary placeholder for service related static methods.
 * Need to encapsulate in another class.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
public class ServiceUtils {

    // converts myalias/1/ into myalias/
    static final Pattern FIND_ALIAS_GROUP_FROM_ALIAS_PATTERN = Pattern.compile("(.*/)\\w+/");
    static final Pattern FIND_ALIAS_GROUP_PATTERN = Pattern.compile("(.*/)");

    private ServiceUtils() {   }

    public static AgentState getAgentState(
            final StateReader stateReader,
            final URI agentId) {
        EtagState<AgentState> etagState = stateReader.get(agentId, AgentState.class);
        return etagState == null ? null : etagState.getState();
    }

    public static ServiceState getServiceState(
            final StateReader stateReader,
            final URI serviceId) {
        EtagState<ServiceState> etagState = stateReader.get(serviceId, ServiceState.class);
        return etagState == null ? null : etagState.getState();
    }

    public static ServiceInstanceState getServiceInstanceState(
            final StateReader stateReader,
            final URI instanceId) {
        try {
            EtagState<ServiceInstanceState> etagState = stateReader.get(instanceId, ServiceInstanceState.class);
            return etagState == null ? null : etagState.getState();

        } catch (RuntimeException e) {
            throw new RuntimeException("Failed to read service instance " + instanceId, e);
        }
    }

    public static URI toTasksHistoryId(URI stateId) {
        return StreamUtils.newURI(stateId.toString() + "_tasks_history");
    }

    public static URI newInstanceId(final URI server, String alias, final LifecycleName name) {
        if (!alias.endsWith("/")) {
            alias += "/";
        }
        validateAlias(alias);
        return URI.create(server + alias + name.getName() + "/");
    }

    private static void validateAlias(String alias) {
        final Matcher matcher = FIND_ALIAS_GROUP_FROM_ALIAS_PATTERN.matcher(alias);
        Preconditions.checkArgument(matcher.find(), "alias %s cannot be parsed", alias);
    }

    private static void validateAliasGroup(String aliasGroup) {
        Preconditions.checkArgument(FIND_ALIAS_GROUP_PATTERN.matcher(aliasGroup).find(),
                "alias group %s cannot be parsed", aliasGroup);
    }
    public static URI newAgentId(final URI server, String alias) {
        if (!alias.endsWith("/")) {
            alias += "/";
        }
        validateAlias(alias);
        return URI.create(server + alias + "cloudmachine/");
    }

    public static URI newServiceId(final URI server, String aliasGroup, LifecycleName name) {
        if (!aliasGroup.endsWith("/")) {
            aliasGroup += "/";
        }
        validateAliasGroup(aliasGroup);
        return URI.create(server + aliasGroup + name.getName() + "/");
    }

    public static String toAliasGroup(String alias) {
        Matcher matcher = FIND_ALIAS_GROUP_FROM_ALIAS_PATTERN.matcher(alias);
        String serviceAlias = null;
        while (matcher.find()) {
            Preconditions.checkArgument(serviceAlias == null, "alias %s cannot be parsed", alias);
            serviceAlias = matcher.group(1);
        }
        Preconditions.checkArgument(serviceAlias != null, "alias %s cannot be parsed", alias);
        return serviceAlias;
    }
}
