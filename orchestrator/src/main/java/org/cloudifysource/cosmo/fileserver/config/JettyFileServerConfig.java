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

package org.cloudifysource.cosmo.fileserver.config;

import org.cloudifysource.cosmo.fileserver.JettyFileServer;
import org.hibernate.validator.constraints.NotEmpty;
import org.hibernate.validator.constraints.Range;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration for {@link org.cloudifysource.cosmo.fileserver.JettyFileServer}.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
@Configuration
public class JettyFileServerConfig {

    @Range(min = 1, max = 65535)
    @Value("${cosmo.file-server.port}")
    protected int port;

    @NotEmpty
    @Value("${cosmo.file-server.resource-base}")
    protected String resourceBase;

    @Bean(destroyMethod = "close")
    public JettyFileServer jettyFileServer() {
        return new JettyFileServer(port, resourceBase);
    }
}
