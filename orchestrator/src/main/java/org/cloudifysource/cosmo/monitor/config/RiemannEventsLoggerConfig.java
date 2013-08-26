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

package org.cloudifysource.cosmo.monitor.config;

import org.cloudifysource.cosmo.monitor.RiemannEventsLogger;
import org.cloudifysource.cosmo.monitor.RiemannPropertyPlaceHolderHelper;
import org.robobninjas.riemann.json.RiemannEventObjectMapper;
import org.robobninjas.riemann.spring.RiemannTcpClientConfiguration;
import org.robobninjas.riemann.spring.RiemannWebsocketClientConfiguration;
import org.robotninjas.riemann.pubsub.RiemannPubSubClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;

import javax.inject.Inject;

/**
 * @author Idan Moyal
 * @since 0.1
 */
@Configuration
@Import({
        RiemannWebsocketClientConfiguration.class,
        RiemannTcpClientConfiguration.class,
        RiemannPropertyPlaceHolderHelperConfig.class
})
public class RiemannEventsLoggerConfig {

    @Inject
    private RiemannPubSubClient riemannClient;

    @Inject
    private RiemannEventObjectMapper objectMapper;

    @Inject
    private RiemannPropertyPlaceHolderHelper riemannPropertyPlaceHolderHelper;

    @Value("${riemann.client.connection.number-of-connection-attempts:60}")
    int numberOfConnectionAttempts;

    @Value("${riemann.client.connection.sleep-before-connection-attempt-milliseconds:1000}")
    int sleepBeforeConnectionAttemptMilliseconds;

    @Bean(destroyMethod = "close")
    public RiemannEventsLogger riemannEventsListener() {
        return new RiemannEventsLogger(
                riemannClient,
                objectMapper,
                numberOfConnectionAttempts,
                sleepBeforeConnectionAttemptMilliseconds,
                riemannPropertyPlaceHolderHelper);
    }

}
