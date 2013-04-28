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
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import java.io.File;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 *
 * @author Idan Moyal
 * @since 0.1
 */
public class VagrantCloudDriverTest {

    private File vagrantRoot;
    private CloudDriver driver;

    @BeforeMethod(alwaysRun = true)
    public void init() {
        vagrantRoot = Files.createTempDir();
        driver = new VagrantCloudDriver(vagrantRoot);
    }

    @AfterMethod(alwaysRun = true)
    public void clean() {
        if (driver != null)
            driver.terminateMachines();
        vagrantRoot.delete();
    }

    @Test(groups = "vagrant")
    public void testMachineLifecycle() {
        VagrantCloudDriver driver = new VagrantCloudDriver(vagrantRoot);
        MachineDetails machine = driver.startMachine(new MachineConfiguration("vm_node", "cosmo"));
        assertThat(machine.getId()).isNotNull();
        assertThat(machine.getIpAddress()).isNotNull();
        driver.stopMachine(machine);
        driver.terminateMachine(machine);
    }

    @Test(groups = "vagrant", expectedExceptions = IllegalArgumentException.class)
    public void testIllegalImage() {
        VagrantCloudDriver driver = new VagrantCloudDriver(vagrantRoot);
        driver.startMachine(new MachineConfiguration("vm_node", "aaaaa"));
    }

}
