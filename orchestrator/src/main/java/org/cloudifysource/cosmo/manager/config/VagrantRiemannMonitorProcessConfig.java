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

package org.cloudifysource.cosmo.manager.config;

import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.utils.ResourceExtractor;
import org.cloudifysource.cosmo.manager.process.VagrantRiemannMonitorProcess;
import org.hibernate.validator.constraints.NotEmpty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;

import javax.annotation.PostConstruct;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Configuration for creating a new {@link org.cloudifysource.cosmo.manager.process.VagrantRiemannMonitorProcess}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
@Configuration
@PropertySource("org/cloudifysource/cosmo/manager/monitor/vagrant-riemann-monitor.properties")
public class VagrantRiemannMonitorProcessConfig {

    private static final String TEMP = System.getProperty("java.io.tmpdir") + "/cosmo";

    private static final String MONITOR_RESOURCE = "monitor";
    private Logger logger = LoggerFactory.getLogger(JettyFileServerForPluginsConfig.class);

    private Path monitorExtractionPath;

    private static final String VAGRANT_MONITOR_NAME = "vagrant-riemann-monitor.py";


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
        String[] command = {
            pythonInterpreter,
            monitorExtractionPath.toAbsolutePath().toString() + "/" + MONITOR_RESOURCE + "/" + VAGRANT_MONITOR_NAME,
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
        return new VagrantRiemannMonitorProcess(command, pidFileName, new File(TEMP));
    }

    @PostConstruct
    public void extractMonitorFile() throws IOException {
        monitorExtractionPath = Paths.get(TEMP);
        ResourceExtractor.extractResource(MONITOR_RESOURCE, monitorExtractionPath);

    }
}
