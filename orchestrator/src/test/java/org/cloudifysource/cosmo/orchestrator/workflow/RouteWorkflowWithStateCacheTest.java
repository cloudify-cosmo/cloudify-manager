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

import com.google.common.collect.ImmutableMap;
import org.cloudifysource.cosmo.statecache.StateCache;
import org.cloudifysource.cosmo.statecache.StateCacheValue;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import java.util.Map;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Tests the integration of ruote workflows and state cache.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class RouteWorkflowWithStateCacheTest {

    StateCache cache;
    RuoteRuntime ruoteRuntime;

    @BeforeMethod
    public void createRuoteRuntime() {

        cache = new StateCache();

        // insert state into jruby runtime properties so that state participant can access it
        Map<String, Object> routeProperties = newMap("state_cache", (Object) cache);

        // start jruby runtime
        ruoteRuntime = RuoteRuntime.createRuntime(routeProperties);
    }

    @AfterMethod(alwaysRun = true)
    public void closeRuoteRuntime() throws Exception {
        if (cache != null) {
            cache.close();
        }
    }

    @Test(timeOut = 120000)
    public void testStateCacheWithWorkflowsAndTimeout() throws Exception {

        final String flow =
            "define flow\n" +
            "  participant ref: \"state\", resource_id: 'general_status',  state: {value: 'good'}, timeout: '1s', " +
                    "on_timeout: 'error'";

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, ruoteRuntime);

        try {
            workflow.execute();
        } catch (org.jruby.embed.InvokeFailedException e) {
            assertThat(e.getMessage()).contains("error triggered from process definition");
        }
    }

    @Test(timeOut = 60000)
    public void testStateCacheParticipantWithResourceIdParameter() {
        cache.put("node1", "reachable", new StateCacheValue("true"));

        final String flow =
                "define flow\n" +
                        "  state resource_id: \"$resource_id\", state: {reachable: \"true\"}\n";

        final RuoteWorkflow workflow = RuoteWorkflow.createFromString(flow, ruoteRuntime);
        workflow.execute(newMap("resource_id", (Object) "node1"));
    }

    private static <T> Map<String, T> newMap(String key, T value) {
        return new ImmutableMap.Builder<String, T>().put(key, value).build();
    }
}
