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
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.io.CharStreams;
import com.google.common.io.Files;
import org.cloudifysource.cosmo.cloud.driver.CloudDriver;
import org.cloudifysource.cosmo.cloud.driver.MachineConfiguration;
import org.cloudifysource.cosmo.cloud.driver.MachineDetails;

import java.io.File;
import java.io.FileFilter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Map;
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

    private final File vagrantRoot;
    private final Map<String, VagrantMachineDetails> machines;

    // TODO: handle specific machine requests concurrency

    public VagrantCloudDriver(File vagrantWorkingDirectory) {
        this.vagrantRoot = vagrantWorkingDirectory;
        if (!vagrantRoot.exists())
            vagrantRoot.mkdirs();
        Preconditions.checkArgument(vagrantRoot.exists());
        this.machines = generateMachinesMap();
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
        Pattern pattern = Pattern.compile("default(.*)");
        Matcher matcher = pattern.matcher(output);
        Preconditions.checkArgument(matcher.find());
        return matcher.group(1).trim();
    }

    @Override
    public MachineDetails startMachine(MachineConfiguration configuration) {
        Preconditions.checkNotNull(configuration.getId());
        Preconditions.checkNotNull(configuration.getImage());
        Preconditions.checkArgument(!machines.containsKey(configuration.getId()));
        final File machineDirectory = new File(vagrantRoot, configuration.getId());
        Preconditions.checkArgument(machineDirectory.mkdirs());
        System.out.println("vagrant:: starting machine in '" + machineDirectory.getAbsolutePath() + "'");
        try {
            new VagrantFileBuilder().box(configuration.getImage()).bridgedNetwork(true).write(machineDirectory);

            vagrant("up", machineDirectory);
            verifyMachineStatus(machineDirectory, VAGRANT_RUNNING);

            final VagrantMachineDetails machineDetails =
                    new VagrantMachineDetails(configuration.getId(), "10.0.0.1", machineDirectory);
            machines.put(configuration.getId(), machineDetails);
            return machineDetails;
        } catch (Exception e) {
            deleteMachineDirectory(machineDirectory);
            throw Throwables.propagate(e);
        }
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
            for (String command : vagrantCommands.split(" ")) {
                commands.add(command);
            }
            final String[] processCommands = commands.toArray(new String[commands.size()]);
            final ProcessBuilder builder = new ProcessBuilder(processCommands).redirectErrorStream(true);
            builder.directory(workingDirectory);

            final Process process = builder.start();
            final String processOutput =
                    CharStreams.toString(new InputStreamReader(process.getInputStream()));

            System.out.println("vagrant:: output:\n" + processOutput);

            int exitCode = process.exitValue();
            Preconditions.checkArgument(exitCode == 0, "vagrant:: exit code is " + exitCode);
            return processOutput;
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }



    /**
     *
     */
    private class VagrantFileBuilder {

        private String box = null;
        private boolean bridgedNetwork = false;

        public void write(File path) {
            Preconditions.checkNotNull(box);
            if (!path.exists())
                path.mkdirs();
            Preconditions.checkArgument(path.exists());
            final File vagrantFile = new File(path, VAGRANT_FILE);
            final StringBuilder content = new StringBuilder("Vagrant::Config.run do |config|\n");
            content.append("\tconfig.vm.box = \"" + box + "\"\n");
            if (bridgedNetwork)
                content.append("\tconfig.vm.network :bridged\n");
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

        public VagrantFileBuilder bridgedNetwork(boolean bridgedNetwork) {
            this.bridgedNetwork = bridgedNetwork;
            return this;
        }
    }

}
