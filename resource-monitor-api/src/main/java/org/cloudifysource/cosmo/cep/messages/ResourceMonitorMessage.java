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

package org.cloudifysource.cosmo.cep.messages;

import com.google.common.base.Objects;

/**
 * A message sent to the resource monitoring server with an indication of which new resource to monitor.
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class ResourceMonitorMessage {

    private String resourceId;

    public ResourceMonitorMessage() {
    }

    public ResourceMonitorMessage(String resourceId) {
        this.resourceId = resourceId;
    }

    public String getResourceId() {
        return resourceId;
    }

    public void setResourceId(String resourceId) {
        this.resourceId = resourceId;
    }

    @Override
    public String toString() {
        return Objects.toStringHelper(this).add("resourceId", resourceId).toString();
    }
}
