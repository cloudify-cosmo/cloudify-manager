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
package org.cloudifysource.cosmo.orchestrator.workflow;

import com.google.common.base.Charsets;
import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.io.Files;
import com.google.common.io.Resources;

import java.io.File;
import java.io.IOException;
import java.net.URL;
import java.util.Collections;
import java.util.Map;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RuoteWorkflow implements Workflow {

    private final RuoteRuntime runtime;
    private final Object parsedWorkflow;

    public static RuoteWorkflow createFromResource(String resourceName, RuoteRuntime runtime) {
        Preconditions.checkNotNull(resourceName);
        Preconditions.checkNotNull(runtime);
        try {
            final URL url = Resources.getResource(resourceName);
            final String workflow = Resources.toString(url, Charsets.UTF_8);
            return new RuoteWorkflow(workflow, runtime);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    public static RuoteWorkflow createFromFile(String path, RuoteRuntime runtime) {
        Preconditions.checkNotNull(path);
        Preconditions.checkNotNull(runtime);
        try {
            final String workflow = Files.toString(new File(path), Charsets.UTF_8);
            return new RuoteWorkflow(workflow, runtime);
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private RuoteWorkflow(String workflow, RuoteRuntime runtime) {
        this.runtime = runtime;
        this.parsedWorkflow = runtime.parseWorkflow(workflow);
    }

    public Object getParsedWorkflow() {
        return parsedWorkflow;
    }

    @Override
    public void execute() {
        execute(Collections.<String, Object>emptyMap());
    }

    @Override
    public void execute(Map<String, Object> workitemFields) {
        runtime.executeWorkflow(this, workitemFields, true /* wait for parsedWorkflow */);
    }

    @Override
    public Object asyncExecute() {
        return asyncExecute(Collections.<String, Object>emptyMap());
    }

    @Override
    public Object asyncExecute(Map<String, Object> workitemFields) {
        return runtime.executeWorkflow(this, workitemFields, false /* wait for parsedWorkflow */);
    }

}
