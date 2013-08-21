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

import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.manager.ManagerLogDescription;
import org.cloudifysource.cosmo.utils.ResourceExtractor;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.robobninjas.riemann.spring.server.RiemannProcess;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.inject.Inject;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * A spring bean that starts and stops the riemann process.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@Configuration
public class RiemannProcessConfiguration {

    @Inject
    private Logger logger;

    private static final String RIEMANN_RESOURCES_PATH = "riemann";

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;


    @Value("${riemann.server.config-resource}")
    private String riemannConfigResourcePath;

    @Bean(destroyMethod = "close")
    public RiemannProcess riemann() throws IOException {
        ResourceExtractor.extractResource(RIEMANN_RESOURCES_PATH,
                Paths.get(temporaryDirectory.get().getAbsolutePath()));
        Path configPath = Paths.get(temporaryDirectory.get().getAbsolutePath(),
                riemannConfigResourcePath);
        logger.info(ManagerLogDescription.LAUNCHING_RIEMANN_CEP);
        return new RiemannProcess(configPath);
    }
}
