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

import com.google.common.collect.Queues;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.config.AgentSSHBootstrapperConfig;
import org.cloudifysource.cosmo.bootstrap.config.BaseConfig;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests the {@link SSHBootstrapper}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@ContextConfiguration(classes = { SSHBootstrapperAgentBootstrapSetupIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class SSHBootstrapperAgentBootstrapSetupIT extends AbstractTestNGSpringContextTests {

    /**
     */
    @Configuration
    @Import({ AgentSSHBootstrapperConfig.class })
    static class Config extends BaseConfig {

        private final BlockingQueue<Boolean> queue = Queues.newArrayBlockingQueue(1);

        // This listener is here only for testing and should not be treated
        // as any valid form of agent process monitoring.
        @Bean
        public LineConsumedListener lineConsumedListener() {
            return new LineConsumedListener() {
                @Override
                public void onLineConsumed(SSHConnectionInfo connectionInfo, String line) {
                    if (line.contains("AgentProcess - Agent started succesfully")) {
                        queue.offer(true);
                    }
                }
            };
        }

    }

    // Tested component
    @Inject
    private SSHBootstrapper bootstrapper;

    @Inject
    private Config config;

    // This test serves more as a demo than as a test and is thus disabled
    @Test(groups = "ssh", timeOut = 10 * 60 * 1000, enabled = false)
    public void testAgentBootstrap() throws ExecutionException, InterruptedException, TimeoutException {
        ListenableFuture<?> future = bootstrapper.bootstrap();

        Futures.addCallback(future, new FutureCallback<Object>() {
            @Override
            public void onSuccess(Object result) {
                config.queue.offer(false); // getting here means something went wrong. script should not terminate.
            }
            @Override
            public void onFailure(Throwable t) {
                config.queue.offer(false); // getting here means something went wrong. (obviously)
            }
        });

        // wait for agent to start
        boolean agentStarted = config.queue.poll(1, TimeUnit.MINUTES);

        // good to go lets disconnect
        future.cancel(true);

        assertThat(agentStarted).isTrue();
    }

}
