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
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
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
        cos("web/1", "machine_set", "--ip", ip, "--username", username, "--keyfile", keyfile);
        installService("web", new LifecycleName("tomcat"), 1);
        execute();
        assertOneTomcatInstance("web", getManagement());
        uninstallService("web", new LifecycleName("tomcat"), 1);
        execute();
        assertTomcatUninstalledGracefully(getManagement(), 1);
    }

    private void installService(String aliasGroup, LifecycleName lifecycleName, int numberOfInstances) {
        cos(aliasGroup + "/", "plan_set", lifecycleName.getName(),
                "--instances", String.valueOf(numberOfInstances),
                "--min_instances", "1",
                "--max_instances", "2");


        for (int i = 1; i <= numberOfInstances; i++) {
            final String alias = aliasGroup + "/" + i + "/";
            startServiceInstance(alias, lifecycleName);
        }
    }

    private void uninstallService(String aliasGroup, LifecycleName lifecycleName, int numberOfInstances) {
        cos(aliasGroup + "/", "plan_unset", lifecycleName.getName());

        for (int i = 1; i <= numberOfInstances; i++) {
            final String alias = aliasGroup + "/" + i + "/";
            cleanServiceInstance(alias, lifecycleName);
        }
    }

    private void startServiceInstance(String alias, LifecycleName lifecycleName) {

        final String prefix = lifecycleName.getName() + "_";
        cos(alias, "lifecycle_set", lifecycleName.getName(),
                prefix + "cleaned<-->" + prefix + "installed<-->" + prefix + "configured->" + prefix + "started" +
                        "," + prefix + "started->" + prefix + "stopped->" + prefix + "cleaned",
                "--begin", prefix + "cleaned",
                "--end", prefix + "started");

        cos(alias, prefix + "started");
    }

    private void cleanServiceInstance(String alias, LifecycleName lifecycleName) {
        final String prefix = lifecycleName.getName() + "_";

        cos(alias, prefix + "cleaned");

        cos(alias, "cloudmachine_terminated");
    }
}
