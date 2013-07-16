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

        RuoteWorkflow useWorkItemsWorkflow =
                RuoteWorkflow.createFromResource("workflows/radial/use_workitems_with_timeout.radial", ruoteRuntime);

        // execute workflow that works with workitems and waits on state
        useWorkItemsWorkflow.execute();
        //TODO: Catch expected exception
    }

    @Test(timeOut = 120000)
    public void testStateCacheWithWorkflows() throws InterruptedException {

        // create new state cache
        cache.put("state0", "status", "good");

        RuoteWorkflow useWorkItemsWorkflow =
                RuoteWorkflow.createFromResource("workflows/radial/use_workitems.radial", ruoteRuntime);
        RuoteWorkflow echoWorkflow =
                RuoteWorkflow.createFromResource("workflows/radial/echo_workflow.radial", ruoteRuntime);

        // execute workflow that works with workitems and waits on state
        final Object useWorkItemsWorkflowId = useWorkItemsWorkflow.asyncExecute(
                newMap("state0", (Object) newMap("status", "good")));


        // sleep some to make sure the above work flow is executed first
        System.out.println("sleep 2000 ms from test");
        Thread.sleep(2000);

        // execute workflow that does almost nothing
        echoWorkflow.execute();

        // the use_workitems workflow waits on this state, this will release the use_workitems workflow
        cache.put("general_status", "value", "good");

        // assert workflow continued properly
        ruoteRuntime.waitForWorkflow(useWorkItemsWorkflowId);
        Map<String, Object> receivedWorkItemFields = RuoteStateCacheTestJavaParticipant.getAndClearLastWorkItems();
        assertThat(((Map<String, String>) receivedWorkItemFields.get("state0")).get("status"))
                .isEqualTo("good");

        // assert state modified by workflow exists
        assertThat(((Map<String, String>) receivedWorkItemFields.get("state0_status_processed")).get("status"))
                .isEqualTo("good");

        // assert workflow after waiting on state change, includes the new state
        assertThat(((Map<String, String>) receivedWorkItemFields.get("general_status")).get("value"))
                .isEqualTo("good");
    }

    @Test(timeOut = 60000)
    public void testStateCacheParticipantWithResourceIdParameter() {
        cache.put("node1", "reachable", "true");

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
