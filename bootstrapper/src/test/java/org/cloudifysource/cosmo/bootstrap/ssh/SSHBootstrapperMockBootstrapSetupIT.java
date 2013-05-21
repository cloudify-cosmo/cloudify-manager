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

import com.google.common.base.Optional;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;
import com.google.common.io.Resources;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.BootstrapSetup;
import org.cloudifysource.cosmo.bootstrap.config.BaseConfig;
import org.cloudifysource.cosmo.bootstrap.config.SSHBootstrapperConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.PropertySource;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.Assert;
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
    @Import({ SSHBootstrapperConfig.class })
    @PropertySource("org/cloudifysource/cosmo/bootstrap/config/mockbootstrapsetuptest.properties")
    static class Config extends BaseConfig {

        @Value("${work.dir}")
        private String workDir;

        @Value("${script.location}")
        private String scriptLocation;

        @Value("${properties.location}")
        private String propertiesLocation;

        @Bean
        public BootstrapSetup bootstrapSetup() {
            return new MockBootstrapSetup(scriptLocation, workDir, propertiesLocation);
        }

    }

    /**
     */
    private static class MockBootstrapSetup extends BootstrapSetup {

        private static final String MOCKENVVAR = "MOCKENVVAR";
        private final List<String> lines = Lists.newLinkedList();
        private final Map<String, String> mockEnv = ImmutableMap.<String, String>builder()
                .put(MOCKENVVAR, "mockenvvarvalue")
                .build();
        private final CountDownLatch outputLatch = new CountDownLatch(2); // 2 expected output lines

        public MockBootstrapSetup(String scriptResourceLocation, String workDirectory,
                                  String propertiesResourceLocation) {
            super(scriptResourceLocation, workDirectory, propertiesResourceLocation);
        }

        @Override
        public Map<String, String> getScriptEnvironment() {
            return mockEnv;
        }

        @Override
        public Optional<LineConsumedListener> getLinedLineConsumedListener() {
            LineConsumedListener listener = new LineConsumedListener() {
                @Override
                public void onLineConsumed(SSHConnectionInfo connectionInfo, String line) {
                    lines.add(line);
                    outputLatch.countDown();
                }
            };
            return Optional.of(listener);
        }

    }

    @Inject
    private MockBootstrapSetup bootstrapSetup;

    // Tested component
    @Inject
    private SSHBootstrapper bootstrapper;

    // Used by test.
    @Inject
    private SSHClient sshClient;

    @Test(groups = "ssh", timeOut = 5 * 1000)
    public void testBootstrap() throws ExecutionException, InterruptedException, TimeoutException, IOException {
        ListenableFuture<?> future = bootstrapper.bootstrap();
        future.get();
        Properties properties = new Properties();
        InputStream propsStream =
                Resources.getResource(bootstrapSetup.getPropertiesResourceLocation().get()).openStream();
        properties.load(propsStream);
        propsStream.close();
        boolean foundEnvVar = false;
        boolean foundProperty = false;

        for (String line : bootstrapSetup.lines) {
            String envLine = MockBootstrapSetup.MOCKENVVAR + "=" + bootstrapSetup.mockEnv.get(MockBootstrapSetup
                    .MOCKENVVAR);
            String propName = properties.stringPropertyNames().iterator().next();
            String propLine = propName + "=" + properties.get(propName);

            if (line.equals(envLine)) {
                foundEnvVar = true;
            }

            if (line.equals(propLine)) {
                foundProperty = true;
            }
        }

        bootstrapSetup.outputLatch.await();
        Assert.assertTrue(foundEnvVar);
        Assert.assertTrue(foundProperty);
    }

}
