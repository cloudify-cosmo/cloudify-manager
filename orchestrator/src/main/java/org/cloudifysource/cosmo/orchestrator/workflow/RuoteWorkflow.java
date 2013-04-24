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

import com.google.common.base.Preconditions;

import java.util.Collections;
import java.util.Map;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RuoteWorkflow implements Workflow {

    private final RuoteRuntime runtime;
    private final String path;

    public static RuoteWorkflow createFromFile(String path) {
        return createFromFile(path, null, null);
    }

    public static RuoteWorkflow createFromFile(String path, Map<String, Object> properties) {
        return createFromFile(path, properties, null);
    }

    public static RuoteWorkflow createFromFile(String path, RuoteRuntime runtime) {
        return createFromFile(path, null, runtime);
    }

    private static RuoteWorkflow createFromFile(String path, Map<String, Object> properties, RuoteRuntime runtime) {
        Preconditions.checkNotNull(path);
        if (runtime == null) {
            runtime = RuoteRuntime.createRuntime(properties);
        }
        return new RuoteWorkflow(path, runtime);
    }

    private RuoteWorkflow(String path, RuoteRuntime runtime) {
        this.path = path;
        this.runtime = runtime;
    }

    public String getPath() {
        return path;
    }

    @Override
    public void execute() {
        execute(Collections.<String, Object>emptyMap());
    }

    @Override
    public void execute(Map<String, Object> workitemFields) {
        runtime.executeWorkflow(this, workitemFields, true /* wait for workflow */);
    }

    @Override
    public Object asyncExecute() {
        return asyncExecute(Collections.<String, Object>emptyMap());
    }

    @Override
    public Object asyncExecute(Map<String, Object> workitemFields) {
        return runtime.executeWorkflow(this, workitemFields, false /* wait for workflow */);
    }

}
