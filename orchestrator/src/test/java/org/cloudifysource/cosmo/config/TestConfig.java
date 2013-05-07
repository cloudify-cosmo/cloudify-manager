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

package org.cloudifysource.cosmo.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.mock.env.MockPropertySource;

import javax.annotation.PostConstruct;
import javax.inject.Inject;
import java.util.Properties;

/**
 * Abstract test spring configuration.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class TestConfig {

    @Inject
    private ConfigurableEnvironment environment;

    @PostConstruct
    public void postConstruct() {
        Properties overridenProperties = overridenProperties();
        if (!overridenProperties.isEmpty())
            environment.getPropertySources().addFirst(new MockPropertySource(overridenProperties));
    }

    protected Properties overridenProperties() {
        return new Properties();
    }

    @Bean
    public static PropertySourcesPlaceholderConfigurer stub() {
        return new PropertySourcesPlaceholderConfigurer();
    }
}
