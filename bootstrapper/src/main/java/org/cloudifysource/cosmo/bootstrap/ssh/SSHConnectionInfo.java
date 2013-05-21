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

package org.cloudifysource.cosmo.bootstrap.ssh;

/**
 * Holds a connection username, host and port.
 * Provides a sensible {@link #toString()} implementation.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class SSHConnectionInfo {

    private final String host;
    private final int port;
    private final String userName;

    public SSHConnectionInfo(String host, int port, String userName) {
        this.host = host;
        this.port = port;
        this.userName = userName;
    }

    public String getHost() {
        return host;
    }

    public String getUserName() {
        return userName;
    }

    public int getPort() {
        return port;
    }

    @Override
    public String toString() {
        return new StringBuilder()
                .append(userName).append("@").append(host).append(":").append(port).toString();
    }

}
