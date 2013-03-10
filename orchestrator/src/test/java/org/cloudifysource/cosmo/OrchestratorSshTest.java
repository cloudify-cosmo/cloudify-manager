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

package org.cloudifysource.cosmo;

import org.cloudifysource.cosmo.mock.MockManagement;
import org.cloudifysource.cosmo.service.id.AliasGroupId;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import static org.cloudifysource.cosmo.AssertServiceState.assertFileRemovedGracefully;
import static org.cloudifysource.cosmo.AssertServiceState.assertOneFileInstance;
import static org.cloudifysource.cosmo.AssertServiceState.assertOneTomcatInstance;
import static org.cloudifysource.cosmo.AssertServiceState.assertTomcatUninstalledGracefully;

/**
 * Unit Tests for {@link org.cloudifysource.cosmo.service.ServiceGridOrchestrator}
 * running with SSH Agent.
 *
 * @author itaif
 * @author Dan Kilman
 * @since 0.1
 */
public class OrchestratorSshTest extends AbstractServiceGridTest<MockManagement> {

    private String ip;
    private String username;
    private String keyfile;
    private boolean ssh;

    @BeforeClass
    @Parameters({"ip", "username", "keyfile", "ssh" })
    public void beforeClass(
            @Optional("myhostname") String ip,
            @Optional("myusername") String username,
            @Optional("mykeyfile.pem") String keyfile,
            @Optional("false") boolean ssh) {

        this.ip = ip;
        this.username = username;
        this.keyfile = keyfile;
        this.ssh = ssh;
        super.getManagement().setUseSshMock(ssh);
    }


    @Override
    protected MockManagement createMockManagement() {
        return new MockManagement();
    }

    private void execute() {
        execute(getManagement().getOrchestratorId(), getManagement().getAgentProbeId());
    }

    @Test(enabled = true)
    public void dataCenterMachineTest() {

        cos("web/1", "machine_set",
                "--ip", ip,
                "--username", username,
                "--keyfile", keyfile);

        cos("web/1", "lifecycle_set", "tomcat",
                "tomcat_cleaned<-->tomcat_installed<-->tomcat_configured->tomcat_started" + "," +
                "tomcat_started->tomcat_stopped->tomcat_cleaned",
                "--begin", "tomcat_cleaned",
                "--end", "tomcat_started");

        cos("web/1", "tomcat_started");

        execute();
        assertOneTomcatInstance(new AliasGroupId("web"), getManagement());

        cos("web/1", "tomcat_cleaned");
        cos("web/1", "machine_unset");

        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    @Parameters({"ip", "username", "keyfile", "targetfilename", "sourcefilename" })
    @Test(enabled = true, groups = "ssh")
    public void copyFileToDataCenterMachineTest(
            @Optional("myhostname") String ip,
            @Optional("myusername") String username,
            @Optional("mykeyfile.pem") String keyfile,
            @Optional("targetfilename") String targetFileName,
            @Optional("sourcefilename") String sourceFileName) {

        cos("web/1", "machine_set",
                "--ip", ip,
                "--username", username,
                "--keyfile", keyfile);

        cos("web/1", "lifecycle_set", "file",
                "file_cleaned<-->file_exists,file_exists<-->file_cleaned",
                targetFileName,
                "--begin", "file_cleaned",
                "--end", "file_exists");

        cos("web/1", "file_exists", targetFileName, "--source", sourceFileName);

        execute();
        assertOneFileInstance(new AliasGroupId("web"), getManagement(), targetFileName);

        cos("web/1", "file_cleaned", targetFileName);
        cos("web/1", "machine_unset");

        execute();
        assertFileRemovedGracefully(getManagement(), targetFileName, 1);
    }


}
