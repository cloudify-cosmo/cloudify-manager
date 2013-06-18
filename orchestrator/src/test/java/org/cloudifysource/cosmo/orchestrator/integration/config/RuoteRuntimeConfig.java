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

import com.google.common.base.Charsets;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.producer.MessageProducer;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.ruote.RuoteRadialVariable;
import org.cloudifysource.cosmo.statecache.RealTimeStateCache;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.inject.Inject;
import java.io.IOException;
import java.net.URI;
import java.net.URL;
import java.util.Map;

/**
 * Creates a new {@link org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class RuoteRuntimeConfig {

    @Value("${cosmo.message-broker.uri}")
    private URI messageBrokerURI;

    @Value("${cosmo.resource-monitor.topic}")
    private String resourceMonitorTopic;

    @Value("${cosmo.resource-provisioner.topic}")
    private String resourceProvisionerTopic;

    @Inject
    private RealTimeStateCache realTimeStateCache;

    @Inject
    private MessageProducer messageProducer;

    @Inject
    private MessageConsumer messageConsumer;

    @Bean
    public RuoteRuntime ruoteRuntime() throws IOException {
        Map<String, Object> runtimeProperties = Maps.newHashMap();
        runtimeProperties.put("state_cache", realTimeStateCache);
        runtimeProperties.put("broker_uri", messageBrokerURI);
        runtimeProperties.put("message_producer", messageProducer);
        runtimeProperties.put("message_consumer", messageConsumer);
        runtimeProperties.put("resource_monitor_topic", resourceMonitorTopic);
        runtimeProperties.put("resource_provisioner_topic", resourceProvisionerTopic);
        final Map<String, Object> variables = Maps.newHashMap();

        final String executeOperationRadial = getContent("ruote/pdefs/execute_operation.radial");
        final String defaultGlobalPlanRadial = getContent("ruote/pdefs/default_global_workflow.radial");

        variables.put("execute_operation", new RuoteRadialVariable(executeOperationRadial));
        variables.put("global_workflow", new RuoteRadialVariable(defaultGlobalPlanRadial));

        return RuoteRuntime.createRuntime(runtimeProperties, variables);
    }

    private static String getContent(String resource) throws IOException {
        final URL url = Resources.getResource(resource);
        return Resources.toString(url, Charsets.UTF_8);
    }

}
