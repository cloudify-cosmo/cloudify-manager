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

package org.cloudifysource.cosmo.orchestrator.integration.config;

import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.messaging.config.MessageBrokerServerConfig;
import org.cloudifysource.cosmo.messaging.config.MessageConsumerTestConfig;
import org.cloudifysource.cosmo.messaging.config.MessageProducerConfig;
import org.cloudifysource.cosmo.monitor.config.MockAgentConfig;
import org.cloudifysource.cosmo.monitor.config.ResourceMonitorServerConfig;
import org.cloudifysource.cosmo.statecache.config.RealTimeStateCacheConfig;
import org.cloudifysource.cosmo.statecache.config.StateCacheConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;

/**
 * Base test class spring configuration.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
@Import({
        RealTimeStateCacheConfig.class,
        StateCacheConfig.class,
        ResourceMonitorServerConfig.class,
        MessageBrokerServerConfig.class,
        MessageConsumerTestConfig.class,
        MessageProducerConfig.class,
        MockAgentConfig.class
})
@PropertySource("org/cloudifysource/cosmo/orchestrator/integration/config/test.properties")
public class BaseOrchestratorIntegrationTestConfig extends TestConfig {

}
