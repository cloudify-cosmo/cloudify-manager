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

import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;

import java.net.URI;

/**
 * The id and the desired state of a planned agent.
 * @author itaif
 * @since 0.1
 *
 */
public class AgentPlan {

    private URI agentId;
    private LifecycleState lifecycleState;
    private String host;
    private String keyFile;
    private String userName;

    public URI getAgentId() {
        return agentId;
    }

    public void setAgentId(URI agentId) {
        this.agentId = agentId;
    }

    public LifecycleState getLifecycleState() {
        return lifecycleState;
    }

    public void setLifecycleState(LifecycleState lifecycleState) {
        this.lifecycleState = lifecycleState;
    }

    public void setHost(String host) {
        this.host = host;
    }

    public String getHost() {
        return host;
    }

    public void setKeyFile(String keyFile) {
        this.keyFile = keyFile;
    }

    public String getKeyFile() {
        return keyFile;
    }

    public void setUserName(String userName) {
        this.userName = userName;
    }

    public String getUserName() {
        return userName;
    }
}
