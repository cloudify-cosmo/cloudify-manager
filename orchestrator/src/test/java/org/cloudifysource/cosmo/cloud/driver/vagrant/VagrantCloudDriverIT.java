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

package org.cloudifysource.cosmo.cloud.driver.vagrant;

import com.google.common.io.Files;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;
import org.cloudifysource.cosmo.cloud.driver.config.VagrantCloudDriverConfig;
import org.cloudifysource.cosmo.config.TestConfig;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.io.File;
import java.util.Properties;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 *
 * @author Idan Moyal
 * @since 0.1
 */
@ContextConfiguration(classes = { VagrantCloudDriverIT.Config.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class VagrantCloudDriverIT extends AbstractTestNGSpringContextTests {

    @Configuration
    @Import({ VagrantCloudDriverConfig.class })
    static class Config extends TestConfig {
        @Override
        protected Properties overridenProperties() {
            File tempDir = Files.createTempDir();
            String vagrantRootPath = tempDir.getAbsolutePath();
            Properties props = super.overridenProperties();
            props.setProperty("cosmo.cloud-driver.vagrant.working-directory", vagrantRootPath);
            return props;
        }
    }

    @Value("${cosmo.cloud-driver.vagrant.working-directory}")
    private File vagrantRoot;

    @Inject
    private CloudDriver driver;

    @Test(groups = "vagrant")
    public void testMachineLifecycle() {
        MachineDetails machine = driver.startMachine(new MachineConfiguration("vm_node", "cosmo"));
        assertThat(machine.getId()).isNotNull();
        assertThat(machine.getIpAddress()).isNotNull();
        driver.stopMachine(machine);
        driver.terminateMachine(machine);
    }

    @Test(groups = "vagrant", expectedExceptions = IllegalArgumentException.class)
    public void testIllegalImage() {
        driver.startMachine(new MachineConfiguration("vm_node", "aaaaa"));
    }

    @AfterMethod(alwaysRun = true, groups = "vagrant")
    public void clean() {
        if (driver != null)
            driver.terminateMachines();
        vagrantRoot.delete();
    }

}
