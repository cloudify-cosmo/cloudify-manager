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

package org.cloudifysource.cosmo.statecache;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteRuntime;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.testng.Assert;
import org.testng.annotations.Test;

import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class StateCacheTest {

    private Map<String, Object> state = new ImmutableMap.Builder<String, Object>()
            .put("state0", new ImmutableMap.Builder<String, Object>()
                    .put("id", "state0")
                    .put("status", "good")
                    .put("substates", new ImmutableList.Builder<String>()
                            .add("state0/substates/substate0")
                            .add("state0/substates/substate1")
                            .build())
                    .build())
            .put("state0/substates/substate0", new ImmutableMap.Builder<String, Object>()
                    .put("id", "state0/substates/substate0")
                    .put("status", "good")
                    .put("substates", new ImmutableList.Builder<String>()
                            .build())
                    .build())
            .put("state0/substates/substate1", new ImmutableMap.Builder<String, Object>()
                    .put("id", "state0/substates/substate1")
                    .put("status", "failed")
                    .put("substates", new ImmutableList.Builder<String>()
                            .build())
                    .build())
            .build();

    @Test
    public void testStateCache() throws InterruptedException {

        // create new state cache
        StateCache cache = new StateCache.Builder()
                .initialState(state)
                .build();

        // hold initial state snapshot
        ImmutableMap<String, Object> cacheSnapshot = cache.snapshot();

        // insert state into jruby runtime properties so that state participant can access it
        Map<String, Object> routeProperties = ImmutableMap.<String, Object>builder().put("state_cache", cache).build();

        // start jruby runtime and load test workflows
        RuoteRuntime ruoteRuntime = RuoteRuntime.createRuntime(routeProperties);
        RuoteWorkflow useWorkItemsWorkflow =
                RuoteWorkflow.createFromResource("workflows/radial/use_workitems.radial", ruoteRuntime);
        RuoteWorkflow echoWorkflow =
                RuoteWorkflow.createFromResource("workflows/radial/echo_workflow.radial", ruoteRuntime);

        // execute workflow that works with workitems and waits on state
        useWorkItemsWorkflow.asyncExecute(cacheSnapshot);

        // sleep some to make sure the above work flow is executed first
        System.out.println("sleep 2000 ms from test");
        Thread.sleep(2000);

        // execute workflow that does almost nothing
        echoWorkflow.asyncExecute();

        // make sure the echo workflow occured and was not blocked
        Assert.assertTrue(RuoteStateCacheTestDummyJavaParticipant.latch.await(5, TimeUnit.SECONDS));

        // the use_workitems workflow waits on this state, this will release the use_workitems workflow
        cache.put("general_status", "good");

        // assert workflow continued properly
        RuoteStateCacheTestJavaParticipant.latch.await(60, TimeUnit.SECONDS);
        Map<String, Object> receivedWorkItemFields = RuoteStateCacheTestJavaParticipant.lastWorkitems;
        Assert.assertNotNull(receivedWorkItemFields);

        // assert original state exists
        for (Map.Entry<String, Object> entry : cacheSnapshot.entrySet()) {
            Assert.assertEquals(receivedWorkItemFields.get(entry.getKey()), entry.getValue());
        }

        // assert state modified by workflow exists
        Assert.assertEquals(receivedWorkItemFields.get("state0_id_processed"),
                            asMap(state.get("state0")).get("id"));
        Assert.assertEquals(receivedWorkItemFields.get("state0_status_processed"),
                            asMap(state.get("state0")).get("status"));
        for (int i = 0; i <= 1; i++) {
            Assert.assertEquals(receivedWorkItemFields.get("state0/substates/substate" + i + "_id_processed"),
                    asMap(state.get("state0/substates/substate" + i)).get("id"));
            Assert.assertEquals(receivedWorkItemFields.get("state0/substates/substate" + i + "_status_processed"),
                    asMap(state.get("state0/substates/substate" + i)).get("status"));
        }

        // assert workflow after waiting on state change, includes the new state
        Assert.assertEquals("good", receivedWorkItemFields.get("general_status"));
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object object) {
        return (Map<String, Object>) object;
    }

}
