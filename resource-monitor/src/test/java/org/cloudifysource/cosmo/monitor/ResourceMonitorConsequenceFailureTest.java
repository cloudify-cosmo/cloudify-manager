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
package org.cloudifysource.cosmo.monitor;

import org.cloudifysource.cosmo.messaging.config.MockMessageConsumerConfig;
import org.cloudifysource.cosmo.messaging.config.MockMessageProducerConfig;
import org.cloudifysource.cosmo.monitor.config.MockAgentConfig;
import org.cloudifysource.cosmo.monitor.config.ResourceMonitorServerConfig;
import org.cloudifysource.cosmo.monitor.config.TestConfig;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.springframework.validation.beanvalidation.BeanValidationPostProcessor;
import org.testng.annotations.Test;

import javax.inject.Inject;

/**
 * Tests {@link ResourceMonitorServer}.
 *
 * @author itaif
 * @since 0.1
 */
@ContextConfiguration(classes = { ResourceMonitorConsequenceFailureTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class ResourceMonitorConsequenceFailureTest extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @PropertySource({ "org/cloudifysource/cosmo/monitor/configuration/test.properties",
                      "org/cloudifysource/cosmo/monitor/configuration/consequence-failure-test.properties" })
    @Import({ ResourceMonitorServerConfig.class,
            MockMessageConsumerConfig.class,
            MockMessageProducerConfig.class,
            MockAgentConfig.class
    })
    static class Config extends TestConfig {
    }

    // component being tested
    @Inject
    private ResourceMonitorServer resourceMonitor;


    @Test(timeOut = 60000)
    public void testAgentReachable() throws InterruptedException {
        Agent agent = new Agent();
        agent.setAgentId("agent_1");
        resourceMonitor.insertFact(agent);
        while (!resourceMonitor.isClosed()) {
            Thread.sleep(100);
        }
    }
}
