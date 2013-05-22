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

package org.cloudifysource.cosmo.bootstrap.ssh;

import com.google.common.collect.Lists;
import com.google.common.io.Resources;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.config.SSHBootstrapperConfig;
import org.cloudifysource.cosmo.bootstrap.config.SSHClientConfig;
import org.cloudifysource.cosmo.bootstrap.config.SessionCommandExecutionMonitorConfig;
import org.cloudifysource.cosmo.bootstrap.config.TestConfig;
import org.fest.assertions.api.Assertions;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeoutException;

/**
 * Tests the {@link org.cloudifysource.cosmo.bootstrap.ssh.SSHBootstrapper}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@ContextConfiguration(classes = { SSHBootstrapperMockBootstrapSetupIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class SSHBootstrapperMockBootstrapSetupIT extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @Import({SSHClientConfig.class,
            SessionCommandExecutionMonitorConfig.class,
            MockSSHBootstrapperConfig.class })
    @PropertySource({ "org/cloudifysource/cosmo/bootstrap/config/connection-test.properties",
            "org/cloudifysource/cosmo/bootstrap/config/mockbootstrapsetuptest.properties" })
    static class Config extends TestConfig {

        private static final String MOCKENVVAR = "MOCKENVVAR";
        private final List<String> lines = Lists.newLinkedList();
        private final CountDownLatch outputLatch = new CountDownLatch(2); // 2 expected output lines

        @Bean
        public LineConsumedListener lineConsumedListener() {
            return new LineConsumedListener() {
                @Override
                public void onLineConsumed(SSHConnectionInfo connectionInfo, String line) {
                    lines.add(line);
                    outputLatch.countDown();
                }
            };
        }

    }

    /**
     */
    @Configuration
    static class MockSSHBootstrapperConfig extends SSHBootstrapperConfig {
        @Override
        protected void addEnviromentVariables(Map<String, String> environmentVariables) {
            super.addEnviromentVariables(environmentVariables);
            environmentVariables.put(Config.MOCKENVVAR, "mockenvvarvalue");
        }
    }

    // Tested component
    @Inject
    private SSHBootstrapper bootstrapper;

    @Inject
    private Config config;

    @Test(groups = "ssh", timeOut = 10 * 1000)
    public void testBootstrap() throws ExecutionException, InterruptedException, TimeoutException, IOException {

        ListenableFuture<?> future = bootstrapper.bootstrap();
        future.get();

        config.outputLatch.await();

        Assertions.assertThat(config.lines.get(0)).isEqualTo(expectedEnviromentVaribleLine());
        Assertions.assertThat(config.lines.get(1)).isEqualTo(expectedPropertiesLine());
    }

    private String expectedPropertiesLine() throws IOException {
        Properties properties = new Properties();
        InputStream propsStream =
                Resources.getResource(bootstrapper.getPropertiesResourceLocation()).openStream();
        properties.load(propsStream);
        propsStream.close();
        String propName = properties.stringPropertyNames().iterator().next();
        return propName + "=" + properties.get(propName);
    }

    private String expectedEnviromentVaribleLine() {
        return Config.MOCKENVVAR + "=" +
                bootstrapper.getScriptEnvironment().get(Config.MOCKENVVAR);
    }

}
