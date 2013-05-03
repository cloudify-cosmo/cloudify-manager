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
 *******************************************************************************/
package org.cloudifysource.cosmo.cep;

import org.drools.io.Resource;

import java.net.URI;


/**
 * Configuration for {@link ResourceMonitorServer}.
 * @author itaif
 * @since 0.1
 */
public class ResourceMonitorServerConfiguration {
    private URI resourceMonitorTopic;
    private URI stateCacheTopic;
    private boolean pseudoClock;
    private Resource droolsResource;
    private URI agentTopic;

    public ResourceMonitorServerConfiguration() {
    }

    public URI getResourceMonitorTopic() {
        return resourceMonitorTopic;
    }

    public URI getAgentTopic() {
        return agentTopic;
    }

    public URI getStateCacheTopic() {
        return stateCacheTopic;
    }

    public boolean isPseudoClock() {
        return pseudoClock;
    }

    public Resource getDroolsResource() {
        return droolsResource;
    }

    public void setResourceMonitorTopic(URI resourceMonitorTopic) {
        this.resourceMonitorTopic = resourceMonitorTopic;
    }

    public void setStateCacheTopic(URI stateCacheTopic) {
        this.stateCacheTopic = stateCacheTopic;
    }

    public void setPseudoClock(boolean pseudoClock) {
        this.pseudoClock = pseudoClock;
    }

    public void setDroolsResource(Resource droolsResource) {
        this.droolsResource = droolsResource;
    }

    public void setAgentTopic(URI agentTopic) {
        this.agentTopic = agentTopic;
    }
}
