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

import org.cloudifysource.cosmo.config.TestConfig;
import org.cloudifysource.cosmo.monitor.config.RiemannPropertyPlaceHolderHelperConfig;
import org.robobninjas.riemann.json.RiemannEvent;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests for riemann place holder replacements.
 *
 * @author Eli Polonsky
 * @since 0.1
 */
@ContextConfiguration(classes = { RiemannPropertyPlaceHolderHelperTest.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class RiemannPropertyPlaceHolderHelperTest extends AbstractTestNGSpringContextTests {

    /**
     * Test Config.
     */
    @Configuration
    @Import({
            RiemannPropertyPlaceHolderHelperConfig.class
    })
    static class Config extends TestConfig {

    }

    @Inject
    private RiemannPropertyPlaceHolderHelper propertyPlaceHolderHelper;

    @Test
    public void testReplaceAllFields() throws Exception {

        RiemannEvent event = new RiemannEvent();
        event.setHost("my_host");
        event.setService("my_service");
        event.setState("my_state");
        event.setMetric("50");

        String original = "host=>${host.value}, service=>${service.value}, state=>${state.value}, " +
                "metric=>${metric.value}";

        String expected = "host=>my_host, service=>my_service, state=>my_state, " +
                "metric=>50";

        String replaced = propertyPlaceHolderHelper.replace(original, event);

        assertThat(replaced).isEqualTo(expected);
    }

    @Test
    public void testReplaceNoFields() {

        RiemannEvent event = new RiemannEvent();
        event.setHost("my_host");
        event.setService("my_service");
        event.setState("my_state");
        event.setMetric("50");

        String original = "host=>${host1.value}, service=>${service1.value}, state=>${state1.value}, " +
                "metric=>${metric1.value}";

        String replaced = propertyPlaceHolderHelper.replace(original, event);

        assertThat(replaced).isEqualTo(original);

    }

}
