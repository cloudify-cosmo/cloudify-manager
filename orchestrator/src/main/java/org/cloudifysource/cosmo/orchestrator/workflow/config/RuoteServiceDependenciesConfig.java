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

package org.cloudifysource.cosmo.orchestrator.workflow.config;

import org.cloudifysource.cosmo.monitor.StateCacheFeeder;
import org.cloudifysource.cosmo.monitor.config.RiemannEventsLoggerConfig;
import org.cloudifysource.cosmo.monitor.config.StateCacheFeederConfig;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.cloudifysource.cosmo.tasks.TaskExecutor;
import org.cloudifysource.cosmo.tasks.config.TaskExecutorConfig;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.validation.beanvalidation.BeanValidationPostProcessor;

import javax.inject.Inject;

/**
 * @author Idan Moyal
 * @since 0.3
 */
@Configuration
@Import({
        StateCacheConfig.class,
        TaskExecutorConfig.class,
        StateCacheConfig.class,
        StateCacheFeederConfig.class,
        RiemannEventsLoggerConfig.class
})
@PropertySource("org/cloudifysource/cosmo/manager/ruote/ruote.properties")
public class RuoteServiceDependenciesConfig {

    @Inject
    private TaskExecutor taskExecutor;

    @Inject
    private StateCache stateCache;

    @Inject
    private StateCacheFeeder stateCacheFeeder;

    @Bean
    public static PropertySourcesPlaceholderConfigurer propertySourcesPlaceholderConfigurer() {
        return new PropertySourcesPlaceholderConfigurer();
    }

    @Bean
    public static BeanValidationPostProcessor beanValidationPostProcessor() {
        return new BeanValidationPostProcessor();
    }


}
