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

import com.google.common.io.Resources;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PostConstruct;
import java.io.File;
import java.net.URL;

/**
 * Configuration for {@link org.cloudifysource.cosmo.fileserver.JettyFileServerTest}.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
@Configuration
public class JettyFileServerTestConfig extends JettyFileServerConfig {

    @Value("${cosmo.file-server.resource-location}")
    private String resourceLocation;

    @PostConstruct
    public void setResourceBase() {
        final URL resource = Resources.getResource(resourceLocation);
        this.resourceBase = new File(resource.getPath()).getParentFile().getAbsolutePath();
    }
}
