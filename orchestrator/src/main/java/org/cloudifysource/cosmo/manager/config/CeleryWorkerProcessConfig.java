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

import com.google.common.base.Throwables;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.tasks.CeleryWorkerProcess;
import org.cloudifysource.cosmo.utils.ResourceExtractor;
import org.cloudifysource.cosmo.utils.config.TemporaryDirectoryConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PostConstruct;
import javax.inject.Inject;
import java.io.IOException;
import java.nio.file.Paths;
import java.util.concurrent.TimeUnit;

/**
 * Creates a new {@link org.cloudifysource.cosmo.tasks.CeleryWorkerProcess}.
 *
 * @author Itai Frenkel
 * @since 0.1
 */
@Configuration
public class CeleryWorkerProcessConfig {

    @Inject
    private Logger logger;

    private static final String RESOURCE_PATH = "celery/app";

    @Value("${celery-worker.timeout-seconds:60}")
    long timeout;

    @Inject
    private TemporaryDirectoryConfig.TemporaryDirectory temporaryDirectory;

    @PostConstruct
    public void extractCeleryApp() {

        try {
            // This will extract the celery app from the resources to the working directory
            ResourceExtractor.extractResource(RESOURCE_PATH, Paths.get(temporaryDirectory.get().getAbsolutePath()));
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    @Bean
    CeleryWorkerProcess celeryWorkerProcess() {
        return new CeleryWorkerProcess("cosmo", temporaryDirectory.get().getAbsolutePath() + "/" + RESOURCE_PATH,
                timeout, TimeUnit.SECONDS);
    }
}
