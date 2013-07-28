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

package org.cloudifysource.cosmo.manager.dsl.config;

import org.cloudifysource.cosmo.manager.dsl.DSLImporter;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.hibernate.validator.constraints.Range;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;

import javax.inject.Inject;
import java.net.InetAddress;
import java.net.UnknownHostException;

/**
 * Creates a new {@link org.cloudifysource.cosmo.manager.dsl.DSLImporter}.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@Configuration
@PropertySource("org/cloudifysource/cosmo/manager/fileserver/jetty.properties")
public class JettyDSLImporterConfig {

    @Range(min = 1, max = 65535)
    @Value("${cosmo.file-server.port}")
    protected int port;

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @Bean
    public DSLImporter dslImporter() throws UnknownHostException {
        String hostAddress = InetAddress.getLocalHost().getHostAddress();
        String locatorPrefix = "http://" + hostAddress + ":" + port + "/";
        return new DSLImporter(temporaryDirectory.get().getAbsolutePath() + "/fileserver",
                temporaryDirectory.get(), locatorPrefix);
    }
}
