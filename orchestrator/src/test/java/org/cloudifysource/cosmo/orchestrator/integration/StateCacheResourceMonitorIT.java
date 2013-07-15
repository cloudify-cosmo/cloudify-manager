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

package org.cloudifysource.cosmo.orchestrator.integration;

import org.cloudifysource.cosmo.monitor.Agent;
import org.cloudifysource.cosmo.monitor.ResourceMonitorServer;
import org.cloudifysource.cosmo.monitor.mock.MockAgent;
import org.cloudifysource.cosmo.orchestrator.integration.config.BaseOrchestratorIntegrationTestConfig;
import org.cloudifysource.cosmo.statecache.DeprecatedStateCache;
import org.cloudifysource.cosmo.statecache.StateCacheReader;
import org.cloudifysource.cosmo.statecache.StateChangeCallback;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.testng.AbstractTestNGSpringContextTests;
import org.testng.annotations.Test;

import javax.inject.Inject;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;

/**
* Tests integration of {@link org.cloudifysource.cosmo.statecache.RealTimeStateCache} with {@link
* org.cloudifysource.cosmo.monitor.ResourceMonitorServer}.
* @author itaif
* @since 0.1
*/
@ContextConfiguration(classes = { BaseOrchestratorIntegrationTestConfig.class })
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
public class StateCacheResourceMonitorIT extends AbstractTestNGSpringContextTests {

    public static final String REACHABLE_PROP = "reachable";

    @Value("${cosmo.test.agent.id}")
    private String agentId;

    //components under test
    @Inject
    private StateCacheReader cache;

    @Inject
    private ResourceMonitorServer resourceMonitor;

    @Inject
    private MockAgent agent;

    @Test(timeOut = 10000)
    public void testNodeOk() throws InterruptedException, ExecutionException {

        Agent agent = new Agent();
        agent.setAgentId(agentId);
        resourceMonitor.insertFact(agent);

        final CountDownLatch success = new CountDownLatch(1);
        String subscriptionId = cache.subscribeToKeyValueStateChanges(null, null,
                agentId,
                new StateChangeCallback() {
                    @Override
                    public boolean onStateChange(Object receiver, Object context, DeprecatedStateCache cache,
                                                 Map<String, Object> newSnapshot) {
                        final Object entry = newSnapshot.get(agentId);
                        if (entry instanceof Map<?, ?>) {
                            final Map<?, ?> state = (Map<?, ?>) entry;
                            if (state.containsKey(REACHABLE_PROP) &&
                                    Boolean.parseBoolean(state.get(REACHABLE_PROP).toString())) {
                                success.countDown();
                            }
                        }
                        return false;
                    }
                });

        success.await();
        cache.removeCallback(subscriptionId);
        this.agent.validateNoFailures();
    }

}
