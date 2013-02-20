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
package org.cloudifysource.cosmo.service.tasks;

import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.service.state.ServiceState;

import java.net.URI;

/**
 * This task removes the reference to the service instance from the service state.
 * @author Itai Frenkel
 * @since 0.1
 */
public class RemoveServiceInstanceFromServiceTask extends Task {

    public RemoveServiceInstanceFromServiceTask() {
        super(ServiceState.class);
    }

    private URI instanceId;

    public URI getInstanceId() {
        return instanceId;
    }

    public void setInstanceId(URI instanceId) {
        this.instanceId = instanceId;
    }

}
