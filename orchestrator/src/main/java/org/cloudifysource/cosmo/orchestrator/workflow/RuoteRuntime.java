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

package org.cloudifysource.cosmo.orchestrator.workflow;

import com.google.common.base.Preconditions;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.jruby.embed.LocalVariableBehavior;
import org.jruby.embed.PathType;
import org.jruby.embed.ScriptingContainer;

import java.net.URL;
import java.util.Collections;
import java.util.Map;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class RuoteRuntime {

    private static final Logger LOGGER = LoggerFactory.getLogger(RuoteRuntime.class);

    private static final String CREATE_DASHBOARD_METHOD_NAME = "create_dashboard";
    private static final String EXECUTE_WORKFLOW_METHOD_NAME = "execute_ruote_workflow";
    private static final String WAIT_FOR_WORKFLOW_METHOD_NAME = "wait_for_workflow";
    private static final String PARSE_WORKFLOW_METHOD_NAME = "parse_workflow";
    private static final String RUOTE_SCRIPT = "scripts/ruby/run_ruote.rb";

    private final ScriptingContainer container;
    private final Object dashboard;
    private final Object receiver;

    private RuoteRuntime(ScriptingContainer container, Object receiver, Object dashboard) {
        this.container = container;
        this.receiver = receiver;
        this.dashboard = dashboard;
    }

    public static RuoteRuntime createRuntime() {
        return createRuntime(null);
    }

    public static RuoteRuntime createRuntime(Map<String, Object> globalProperties,
                                             Map<String, Object> dashboardVariables) {
        return createRuntime(globalProperties, dashboardVariables, null);
    }

    public static RuoteRuntime createRuntime(Map<String, Object> globalProperties,
                                             Map<String, Object> dashboardVariables,
                                             ClassLoader rubyClassLoader) {
        try {
            LOGGER.debug("Creating ruote runtime...");
            final ScriptingContainer container = new ScriptingContainer(LocalVariableBehavior.PERSISTENT);
            updateLibraryPath(container, "ruote-gems/gems", rubyClassLoader);
            updateLibraryPath(container, "scripts", rubyClassLoader);
            container.put("$ruote_properties", globalProperties != null ? globalProperties : Maps.newHashMap());
            container.put("$logger", LOGGER);
            final Object receiver = container.runScriptlet(PathType.CLASSPATH, RUOTE_SCRIPT);
            final Object dashboard =
                    container.callMethod(receiver, CREATE_DASHBOARD_METHOD_NAME, dashboardVariables);
            return new RuoteRuntime(container, receiver, dashboard);
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    public static RuoteRuntime createRuntime(Map<String, Object> globalProperties) {
        return createRuntime(globalProperties, Collections.<String, Object>emptyMap());
    }

    private static void updateLibraryPath(ScriptingContainer container, String resourcesRoot, ClassLoader loader) {
        URL gemsResource;
        if (loader == null) {
            gemsResource = Resources.getResource(resourcesRoot);
        } else {
            gemsResource = loader.getResource(resourcesRoot);
        }
        Preconditions.checkNotNull(gemsResource);
        final String resourcePath = gemsResource.getPath();
        container.runScriptlet("Dir['" + resourcePath + "/**/*'].each { |dir| $: << dir }");
    }

    public Object executeWorkflow(RuoteWorkflow workflow, Map<String, Object> workitemFields,
                                  boolean waitForWorkflow) {
        try {
            LOGGER.debug("Executing workflow: \n'{}'\n with workitem.fields: {}", workflow.getParsedWorkflow(),
                    workitemFields);
            return container.callMethod(receiver, EXECUTE_WORKFLOW_METHOD_NAME, dashboard, workflow.getParsedWorkflow(),
                    workitemFields, waitForWorkflow);
        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    public void waitForWorkflow(Object wfid) {
        container.callMethod(receiver, WAIT_FOR_WORKFLOW_METHOD_NAME, dashboard, wfid);
    }

    public Object parseWorkflow(String workflow) {
        return container.callMethod(receiver, PARSE_WORKFLOW_METHOD_NAME, workflow);
    }
}
