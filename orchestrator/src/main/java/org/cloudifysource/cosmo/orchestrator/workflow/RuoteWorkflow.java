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
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.jruby.embed.LocalVariableBehavior;
import org.jruby.embed.PathType;
import org.jruby.embed.ScriptingContainer;

import java.net.URL;
import java.util.Collections;
import java.util.Map;

/**
 * @author Idan Moyal
 * @since 0.1
 */
public class RuoteWorkflow implements Workflow {

    private static final String EXECUTE_WORKFLOW_METHOD_NAME = "execute_ruote_workflow";
    private static final String RUOTE_SCRIPT = "scripts/ruby/run_ruote.rb";

    private final String path;
    private final Map<String, Object> properties;

    public static RuoteWorkflow createFromFile(String path) {
        return createFromFile(path, null);
    }

    public static RuoteWorkflow createFromFile(String path, Map<String, Object> properties) {
        return new RuoteWorkflow(path, properties);
    }

    private RuoteWorkflow(String path, Map<String, Object> properties) {
        this.path = path;
        this.properties = properties;
    }

    @Override
    public void execute() {
        execute(Collections.<String, Object>emptyMap());
    }

    @Override
    public void execute(Map<String, Object> workitemFields) {
        try {
            final URL workflowResource = Resources.getResource(path);
            Preconditions.checkNotNull(workflowResource);
            final String workflow = Resources.toString(workflowResource, Charsets.UTF_8);
            final ScriptingContainer container = new ScriptingContainer(LocalVariableBehavior.PERSISTENT);

            final URL resource = Resources.getResource("ruote-gems/gems");
            Preconditions.checkNotNull(resource);
            final String resourcePath = resource.getPath();

            container.runScriptlet("Dir['" + resourcePath + "/**/*'].each { |dir| $: << dir }");
            container.put("$ruote_properties", properties != null ? properties : Maps.newHashMap());

            Object receiver = container.runScriptlet(PathType.CLASSPATH, RUOTE_SCRIPT);

            container.callMethod(receiver, EXECUTE_WORKFLOW_METHOD_NAME, workflow, workitemFields);

        } catch (Exception e) {
            Throwables.propagate(e);
        }
    }
}
