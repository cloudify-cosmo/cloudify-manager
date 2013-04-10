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
package org.cloudifysource.cosmo.service.tasks;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.google.common.collect.Iterables;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import org.cloudifysource.cosmo.Task;
import org.cloudifysource.cosmo.service.id.AliasGroupId;
import org.cloudifysource.cosmo.service.id.AliasId;
import org.cloudifysource.cosmo.service.state.ServiceGridOrchestratorState;

import java.util.List;
import java.util.Map;

/**
 * A task for the orchestrator to change the deployment plan.
 * The task is weakly typed and follows the convention of commandline arguments and options.
 *
 * @author itaif
 * @since 0.1
 */
public class UpdateDeploymentCommandlineTask extends Task {

    private List<String> arguments;
    private Map<String, String> options;

    /**
     * Converts the arguments into a command line interface task.
     */
    public static UpdateDeploymentCommandlineTask cli(AliasGroupId aliasGroupId, String ... args) {
        List<String> argsl = Lists.newArrayList(args);
        argsl.add(0, aliasGroupId.toString());
        return new UpdateDeploymentCommandlineTask(argsl);
    }

    /**
     * Converts the arguments into a command line interface task.
     */
    public static UpdateDeploymentCommandlineTask cli(AliasId aliasId, String ... args) {
        List<String> argsl = Lists.newArrayList(args);
        argsl.add(0, aliasId.toString());
        return new UpdateDeploymentCommandlineTask(argsl);
    }

    /**
     * Converts the arguments into a command line interface task.
     */
    public static UpdateDeploymentCommandlineTask cli(String ... args) {
        List<String> argsl = Lists.newArrayList(args);
        return new UpdateDeploymentCommandlineTask(argsl);
    }

    private UpdateDeploymentCommandlineTask(Iterable<String> args) {
        this();
        for (int i = 0; i < Iterables.size(args); i++) {
            final String arg = Iterables.get(args, i);
            if (!arg.startsWith("--")) {
                addArgument(arg);
            } else {
                final String optionName = arg.substring(2);
                i++;
                final String optionValue = Iterables.get(args, i);
                addOption(optionName, optionValue);
            }
        }
    }

    public UpdateDeploymentCommandlineTask() {
        super(ServiceGridOrchestratorState.class);
        arguments = Lists.newArrayList();
        options = Maps.newLinkedHashMap();
    }

    @JsonIgnore
    public void addArgument(String arg) {
        this.arguments.add(arg);
    }

    public void addOption(String name, String value) {
        this.options.put(name, value);
    }

    public List<String> getArguments() {
        return arguments;
    }

    public void setArguments(List<String> arguments) {
        this.arguments = arguments;
    }

    public Map<String, String> getOptions() {
        return options;
    }

    public void setOptions(Map<String, String> options) {
        this.options = options;
    }
}
