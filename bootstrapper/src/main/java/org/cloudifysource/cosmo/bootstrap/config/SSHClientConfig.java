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

package org.cloudifysource.cosmo.bootstrap.config;

import org.cloudifysource.cosmo.bootstrap.ssh.SSHClient;
import org.cloudifysource.cosmo.bootstrap.ssh.SessionCommandExecutionMonitor;
import org.hibernate.validator.constraints.NotEmpty;
import org.hibernate.validator.constraints.Range;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.inject.Inject;

/**
 * Creates a new {@link org.cloudifysource.cosmo.bootstrap.ssh.SSHClient}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class SSHClientConfig {

    @NotEmpty
    @Value("${cosmo.ssh-client.host}")
    private String host;

    @Range(min = 1, max = 65535)
    @Value("${cosmo.ssh-client.port:22}")
    private int port;

    @NotEmpty
    @Value("${cosmo.ssh-client.username}")
    private String userName;

    @NotEmpty
    @Value("${cosmo.ssh-client.key-file}")
    private String keyFile;

    @Inject
    private SessionCommandExecutionMonitor sessionCommandExecutionMonitor;

    @Bean(destroyMethod = "close")
    public SSHClient sshClient() {
        return new SSHClient(host, port, userName, keyFile, sessionCommandExecutionMonitor);
    }

}
