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

package org.cloudifysource.cosmo.orchestrator.integration.config;

import com.google.common.io.Resources;
import org.cloudifysource.cosmo.orchestrator.integration.monitor.VagrantRiemannMonitorProcess;
import org.hibernate.validator.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.File;

/**
 * Configuration for creating a new {@link VagrantRiemannMonitorProcess}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
public class VagrantRiemannMonitorProcessConfig {

    // Configuration to execute the monitor
    @NotEmpty
    @Value("${cosmo.monitor.vagrant.python_interpreter:python}")
    private String pythonInterpreter;

    // Configuration passed to the monitor process
    @NotEmpty
    @Value("${cosmo.monitor.vagrant.ssh_host:127.0.0.1}")
    private String vagrantSSHHost;

    @Value("${cosmo.monitor.vagrant.ssh_port:2222}")
    private Integer vagrantSSHPort;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.ssh_user:vagrant}")
    private String vagrantSSHUser;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.ssh_keyfile:~/.vagrant.d/insecure_private_key}")
    private String vagrantSSHKeyFile;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.host_id}")
    private String hostId;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.riemann_host:localhost}")
    private String riemannHost;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.riemann_port:5555}")
    private String riemannPort;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.riemann_transport:tcp}")
    private String riemannTransport;

    @Value("${cosmo.monitor.vagrant.monitor_interval:5}")
    private Integer monitorInterval;

    @NotEmpty
    @Value("${cosmo.monitor.vagrant.nic:eth1}")
    private String vagrantNic;

    @Bean(destroyMethod = "close")
    public VagrantRiemannMonitorProcess vagrantRiemannMonitorProcess() {
        long currentTime = System.currentTimeMillis();
        String pidFileName = "process.pid." + currentTime;
        String monitorResource = "monitor/vagrant-riemann-monitor.py";
        String monitorFile = Resources.getResource(monitorResource).getPath();
        String[] command = {
            pythonInterpreter,
            monitorFile,
            "--tag=" + "name=" + hostId,
            "--riemann_host=" + riemannHost,
            "--riemann_port=" + riemannPort,
            "--riemann_transport=" + riemannTransport,
            "--ssh_host=" + vagrantSSHHost,
            "--ssh_port=" + vagrantSSHPort,
            "--ssh_user=" + vagrantSSHUser,
            "--ssh_keyfile=" + vagrantSSHKeyFile,
            "--monitor_interval=" + monitorInterval,
            "--vagrant_nic=" + vagrantNic,
            "--pid_file=" + pidFileName
        };
        return new VagrantRiemannMonitorProcess(command, pidFileName, new File(System.getProperty("java.io.tmpdir")));
    }

}
