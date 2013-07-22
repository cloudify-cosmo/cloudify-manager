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

package org.cloudifysource.cosmo.manager.config;

import org.cloudifysource.cosmo.fileserver.config.JettyFileServerConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;

import javax.annotation.PostConstruct;
import javax.inject.Inject;

/**
 * Creates a new {@link JettyFileServerConfig}.
 *
 * Sets the resourceBase of the file server to a temporary directory created by {@link TemporaryDirectoryConfig}
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@Configuration
@Import({
        TemporaryDirectoryConfig.class,
})
@PropertySource("org/cloudifysource/cosmo/manager/fileserver/jetty.properties")
public class JettyFileServerForPluginsConfig extends JettyFileServerConfig {

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @PostConstruct
    public void setResourceBase() {
        this.resourceBase = temporaryDirectory.get().getAbsolutePath();
    }
}
