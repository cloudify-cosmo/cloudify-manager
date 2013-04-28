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

import com.google.common.base.Charsets;
import com.google.common.base.Objects;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.io.Files;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileFilter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class VagrantCloudDriver implements CloudDriver {

    private static final String VAGRANT_FILE = "Vagrantfile";
    private static final String VAGRANT_RUNNING = "running";
    private static final String VAGRANT_STOPPED = "poweroff";
    private static final String VAGRANT_TERMINATED = "not created";
    private static final String VAGRANT_DEFAULT_BOX = "cosmo";
    private static final String VAGRANT_MACHINE_IP_PREFIX = "10.0.0.";
    private static final String PUPPET_MANIFESTS_DIRECTORY = "manifests";
    private static final String TOMCAT_MANIFEST_NAME = "tomcat";

    private final File vagrantRoot;
    private final Map<String, VagrantMachineDetails> machines;
    private final AtomicInteger machinesCounter;

    // TODO: handle specific machine requests concurrency

    public VagrantCloudDriver(File vagrantWorkingDirectory) {
        this.vagrantRoot = vagrantWorkingDirectory;
        if (!vagrantRoot.exists())
            vagrantRoot.mkdirs();

        Preconditions.checkArgument(vagrantRoot.exists());
        this.machinesCounter = new AtomicInteger(1);
        this.machines = generateMachinesMap();
        Map<String, VagrantBox> boxes = getInstalledBoxes();
        if (!boxes.containsKey(VAGRANT_DEFAULT_BOX)) {
            prepareAndInstallDefaultBoxImage();
        }
    }

    private void prepareAndInstallDefaultBoxImage() {
        final MachineConfiguration config = new MachineConfiguration(VAGRANT_DEFAULT_BOX, VAGRANT_DEFAULT_BOX);
        VagrantMachineDetails details = null;
        try {
            System.out.println(
                    "vagrant installation does not contain a '" + VAGRANT_DEFAULT_BOX + "' box. The box will " +
                            "be downloaded and installed - this might take several minutes...");
            final Properties props = new Properties();
            final InputStream stream = getClass().getResourceAsStream("/vagrant/vagrant.properties");
            props.load(stream);
            Preconditions.checkArgument(props.containsKey("image"));
            final String imageLocation = (String) props.get("image");
            System.out.println("Installing box from: '" + imageLocation + "'");
            if (imageLocation.contains("http")) {
                vagrant(String.format("box add %s %s", VAGRANT_DEFAULT_BOX, imageLocation), vagrantRoot);
            } else {
                final File boxFile = new File(imageLocation);
                Preconditions.checkArgument(boxFile.exists());
                vagrant(String.format("box add %s %s", VAGRANT_DEFAULT_BOX, boxFile.getName()),
                        boxFile.getParentFile());
            }
            final Map<String, VagrantBox> installedBoxes = getInstalledBoxes();
            Preconditions.checkArgument(installedBoxes.containsKey(VAGRANT_DEFAULT_BOX));
            final VagrantBox defaultBox = installedBoxes.get(VAGRANT_DEFAULT_BOX);

            // When creating a machine an image will be exported of - we don't assign it an ip address
            // since there's an issue with vagrant and centos which prevents a created machine of the new image
            // to start due to a failure in network configuration.
            details = startMachine(config, false);

            vagrant("package", details.getDirectory());

            vagrant(String.format("box remove %s %s", defaultBox.getName(), defaultBox.getProvider()), vagrantRoot);

            final String boxPath = new File(details.getDirectory(), "package.box").getAbsolutePath();
            vagrant(String.format("box add %s %s", VAGRANT_DEFAULT_BOX, boxPath), vagrantRoot);

        } catch (Exception e) {
            if (details != null) {
                try {
                    terminateMachine(details);
                } catch (Exception ee) {
                }
            }
            Throwables.propagate(e);
        }
    }

    private Map<String, VagrantBox> getInstalledBoxes() {
        final String output = vagrant("box list", vagrantRoot);
        final String[] boxes = output.split(System.getProperty("line.separator"));
        final String boxPattern = "([^\\s]*)\\s*\\((\\w*)\\)";
        final Pattern pattern = Pattern.compile(boxPattern);
        final Map<String, VagrantBox> vagrantBoxes = Maps.newHashMap();
        for (String box : boxes) {
            final Matcher matcher = pattern.matcher(box);
            Preconditions.checkArgument(matcher.find());
            VagrantBox vagrantBox = new VagrantBox(matcher.group(1), matcher.group(2));
            vagrantBoxes.put(vagrantBox.getName(), vagrantBox);
        }
        return vagrantBoxes;
    }

    /**
     *
     */
    private static class VagrantBox {

        private final String name;
        private final String provider;

        public VagrantBox(String name, String provider) {
            this.name = name;
            this.provider = provider;
        }

        private String getName() {
            return name;
        }

        private String getProvider() {
            return provider;
        }
    }

    private Map<String, VagrantMachineDetails> generateMachinesMap() {
        final File[] vagrantsDirs = vagrantRoot.listFiles(new FileFilter() {
            @Override
            public boolean accept(File path) {
                if (path.isDirectory()) {
                    File vagrantFile = new File(path, VAGRANT_FILE);
                    return vagrantFile.exists();
                }
                return false;
            }
        });
        final Map<String, VagrantMachineDetails> machines = Maps.newConcurrentMap();
        if (vagrantsDirs != null) {
            for (File dir : vagrantsDirs) {
                // TODO: get vagrant machine ip address from Vagrantfile
                machines.put(dir.getName(), new VagrantMachineDetails(dir.getName(), "10.0.0.1", dir));
            }
        }
        return machines;
    }

    private String getMachineStatus(File machineDirectory) {
        final String output = vagrant("status", machineDirectory);
        Pattern pattern = Pattern.compile("default(.*)\\(.*");
        Matcher matcher = pattern.matcher(output);
        Preconditions.checkArgument(matcher.find());
        return matcher.group(1).trim();
    }

    private VagrantMachineDetails startMachine(MachineConfiguration configuration, boolean assignIpAddress) {
        Preconditions.checkNotNull(configuration.getId());
        Preconditions.checkNotNull(configuration.getImage());
        Preconditions.checkArgument(!machines.containsKey(configuration.getId()));
        final File machineDirectory = new File(vagrantRoot, configuration.getId());
        Preconditions.checkArgument(machineDirectory.mkdirs());
        final int machineNumber = machinesCounter.incrementAndGet();
        final String ip = VAGRANT_MACHINE_IP_PREFIX + machineNumber;
        System.out.println("vagrant: starting machine in '" + machineDirectory.getAbsolutePath() + "' with ip: " + ip);
        try {
            new VagrantFileBuilder()
                    .box(configuration.getImage())
                    .ip(assignIpAddress ? ip : null)
                    .manifest("tomcat")
                    .write(machineDirectory);

            vagrant("up", machineDirectory);
            verifyMachineStatus(machineDirectory, VAGRANT_RUNNING);
            vagrant("ssh -c \"sudo iptables -F\"", machineDirectory);

            final VagrantMachineDetails machineDetails =
                    new VagrantMachineDetails(configuration.getId(), ip, machineDirectory);
            machines.put(configuration.getId(), machineDetails);
            return machineDetails;
        } catch (Exception e) {
            VagrantMachineDetails details =
                    new VagrantMachineDetails(configuration.getId(), assignIpAddress ? ip : null, machineDirectory);
            try {
                terminateMachine(details);
            } catch (Exception ee) {
            }
            throw Throwables.propagate(e);
        }
    }

    @Override
    public VagrantMachineDetails startMachine(MachineConfiguration configuration) {
        return startMachine(configuration, true);
    }

    @Override
    public void stopMachine(MachineDetails machine) {
        Preconditions.checkArgument(machine instanceof VagrantMachineDetails);
        final VagrantMachineDetails details = (VagrantMachineDetails) machine;
        Preconditions.checkArgument(details.getDirectory().exists());
        vagrant("halt", details.getDirectory());
        verifyMachineStatus(details.getDirectory(), VAGRANT_STOPPED);
    }

    @Override
    public void terminateMachine(MachineDetails machine) {
        Preconditions.checkArgument(machine instanceof VagrantMachineDetails);
        final VagrantMachineDetails details = (VagrantMachineDetails) machine;
        Preconditions.checkArgument(details.getDirectory().exists());
        vagrant("destroy -f", details.getDirectory());
        verifyMachineStatus(details.getDirectory(), VAGRANT_TERMINATED);
        machines.remove(details.getId());
        deleteMachineDirectory(details.getDirectory());
    }

    @Override
    public void terminateMachines() {
        for (VagrantMachineDetails machineDetails : machines.values()) {
            terminateMachine(machineDetails);
        }
    }

    private void deleteMachineDirectory(File directory) {
        File[] files = directory.listFiles();
        if (files != null) {
            for (File file : files) {
                if (file.isDirectory())
                    deleteMachineDirectory(file);
                file.delete();
            }
            directory.delete();
        }
    }

    private void verifyMachineStatus(File directory, String status) {
        final String machineStatus = getMachineStatus(directory);
        Preconditions.checkArgument(status.equals(machineStatus), "machine status is expected to be '%s' but is '%s'",
                status, machineStatus);
    }

    private String vagrant(String vagrantCommands, File workingDirectory) {
        try {
            // TODO: write equivalent code for linux
            final ArrayList<String> commands = Lists.newArrayList("cmd", "/c", "vagrant");
            final String cmdPattern = "(-?\\w+)|(\\\".*\\\")";
            final Pattern pattern = Pattern.compile(cmdPattern);
            final Matcher matcher = pattern.matcher(vagrantCommands);
            while (matcher.find()) {
                if (matcher.group(1) != null)
                    commands.add(matcher.group(1));
                else if (matcher.group(2) != null)
                    commands.add(matcher.group(2));
            }
            final String[] processCommands = commands.toArray(new String[commands.size()]);
            final ProcessBuilder builder = new ProcessBuilder(processCommands).redirectErrorStream(true);
            builder.directory(workingDirectory);

            final Process process = builder.start();
            final BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            final StringBuilder processOutput = new StringBuilder();
            try {
                String line;
                while ((line = reader.readLine()) != null) {
                    System.out.println("vagrant-output:: " + line);
                    processOutput.append(line);
                    processOutput.append(System.getProperty("line.separator"));
                }
            } finally {
                reader.close();
            }
            int exitCode = process.exitValue();
            Preconditions.checkArgument(exitCode == 0, "vagrant:: exit code is " + exitCode);
            return processOutput.toString();
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    /**
     *
     */
    private class VagrantFileBuilder {

        private String box;
        private String ip;
        private String manifest;

        public void write(File path) {
            Preconditions.checkNotNull(box);
            if (!path.exists())
                path.mkdirs();
            Preconditions.checkArgument(path.exists());
            final File vagrantFile = new File(path, VAGRANT_FILE);
            final StringBuilder content = new StringBuilder("Vagrant::Config.run do |config|\n");
            content.append("\tconfig.vm.box = \"" + box + "\"\n");
            if (ip != null)
                content.append("\tconfig.vm.network :hostonly, \"" + ip + "\"\n");
            if (Objects.equal(manifest, TOMCAT_MANIFEST_NAME)) {
                content.append("\tconfig.vm.provision :puppet do |puppet|\n");
                content.append("\t\tpuppet.manifests_path = \"manifests\"\n");
                content.append("\t\tpuppet.manifest_file = \"" + manifest + ".pp" + "\"\n");
                content.append("\tend\n");
                final File manifestsDir = new File(path, PUPPET_MANIFESTS_DIRECTORY);
                manifestsDir.mkdirs();
                final String manifestContent = "group { 'puppet': ensure => 'present' }\n" +
                        "class java_6 {\n" +
                        "\tpackage { \"java-1.7.0-openjdk.x86_64\":\n" +
                        "\t\tensure => installed\n" +
                        "\t}\n" +
                        "}\n" +
                        "class tomcat_6 {\n" +
                        "\tpackage { \"tomcat6\":\n" +
                        "\t\tensure => installed,\n" +
                        "\t\trequire => Package['java-1.7.0-openjdk.x86_64']\n" +
                        "\t}\n" +
                        "}\n" +
                        "include java_6\n" +
                        "include tomcat_6";
                try {
                    Files.write(manifestContent.getBytes(Charsets.UTF_8), new File(manifestsDir, manifest + ".pp"));
                } catch (IOException e) {
                    Throwables.propagate(e);
                }
            }
            content.append("end\n");
            try {
                Files.write(content.toString().getBytes(Charsets.UTF_8), vagrantFile);
            } catch (IOException e) {
                Throwables.propagate(e);
            }
        }

        public VagrantFileBuilder box(String box) {
            this.box = box;
            return this;
        }

        public VagrantFileBuilder ip(String ip) {
            this.ip = ip;
            return this;
        }

        public VagrantFileBuilder manifest(String manifest) {
            this.manifest = manifest;
            return this;
        }
    }

}
