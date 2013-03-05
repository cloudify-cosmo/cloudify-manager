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
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

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

    @Override
    protected MockManagement createMockManagement() {
        //TODO: Enable ssh
        return new MockManagement();
    }

    private void execute() {
        execute(getManagement().getOrchestratorId(), getManagement().getAgentProbeId());
    }

    @Parameters({"ip", "username", "keyfile"})
    @Test(enabled = true)
    public void dataCenterMachineTest(
            @Optional("myhostname") String ip,
            @Optional("myusername") String username,
            @Optional("mykeyfile.pem") String keyfile) {

        cos("web", "plan_set", "tomcat",
                "--instances", "1",
                "--min_instances", "1",
                "--max_instances", "2");

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
        assertOneTomcatInstance("web", getManagement());

        cos("web", "plan_unset", "tomcat");
        cos("web/1", "tomcat_cleaned");
        cos("web/1", "machine_unset");

        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }
}
