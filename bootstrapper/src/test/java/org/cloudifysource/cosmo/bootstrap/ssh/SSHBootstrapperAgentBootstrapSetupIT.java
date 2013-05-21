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

import com.google.common.util.concurrent.ListenableFuture;
import org.cloudifysource.cosmo.bootstrap.config.AgentBootstrapSetupConfig;
import org.cloudifysource.cosmo.bootstrap.config.BaseConfig;
import org.cloudifysource.cosmo.bootstrap.config.SSHBootstrapperConfig;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.concurrent.ExecutionException;

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
    @Import({
            AgentBootstrapSetupConfig.class,
            SSHBootstrapperConfig.class })
    static class Config extends BaseConfig { }

    // Tested component
    @Inject
    private SSHBootstrapper bootstrapper;

    // Used by test.
    @Inject
    private SSHClient sshClient;

    @Test(groups = "ssh", timeOut = 50 * 1000)
    public void testAgentBootstrap() throws ExecutionException, InterruptedException {
        ListenableFuture<?> future = bootstrapper.bootstrap();

    }

}
