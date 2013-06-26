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

package org.cloudifysource.cosmo.orchestrator.integration.monitor;

import java.net.InetSocketAddress;

/**
 * Simple data holder for the {@link MockPortKnocker}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class PortKnockingDescriptor {

    private final InetSocketAddress socketAddress;
    private final String resourceId;

    public PortKnockingDescriptor(InetSocketAddress socketAddress, String resourceId) {
        this.socketAddress = socketAddress;
        this.resourceId = resourceId;
    }

    public InetSocketAddress getSocketAddress() {
        return socketAddress;
    }

    public String getResourceId() {
        return resourceId;
    }

    @Override
    public String toString() {
        return getSocketAddress() + "[" + resourceId + "]";
    }
}
