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
package org.cloudifysource.cosmo;

import com.google.common.base.Charsets;
import com.google.common.base.Joiner;
import com.google.common.base.Optional;
import com.google.common.collect.Lists;
import com.google.common.io.Resources;
import org.cloudifysource.cosmo.agent.state.AgentState;
import org.cloudifysource.cosmo.agent.tasks.PingAgentTask;
import org.cloudifysource.cosmo.mock.ssh.MockSSHAgent;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleName;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleState;
import org.cloudifysource.cosmo.service.lifecycle.LifecycleStateMachine;
import org.cloudifysource.cosmo.service.state.ServiceInstanceState;
import org.cloudifysource.cosmo.service.tasks.RecoverServiceInstanceStateTask;
import org.cloudifysource.cosmo.service.tasks.RemoveServiceInstanceFromAgentTask;
import org.cloudifysource.cosmo.service.tasks.ServiceInstanceTask;
import org.cloudifysource.cosmo.service.tasks.SetInstancePropertyTask;
import org.testng.Assert;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.io.IOException;
import java.net.URI;
import java.net.URL;

/**
 * Unit Tests for {@link org.cloudifysource.cosmo.mock.ssh.MockSSHAgent}.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class MockSSHAgentTest {

    // TODO SSH verify service instance state content

    private final URI agentId = URI.create("http://www.server.com/agent");
    private final URI serviceId = URI.create("http://www.server.com/alias/service");
    private final URI instanceId = URI.create("http://www.server.com/alias/1/service");
    private MockSSHAgent agent;
    private AgentState state;

    @Parameters({"ip", "username", "keyfile" })
    @BeforeMethod
    public void before(
            @org.testng.annotations.Optional("myhostname") String ip,
            @org.testng.annotations.Optional("myusername") String username,
            @org.testng.annotations.Optional("mykeyfile.pem") String keyfile) {
        state = new AgentState();
        state.setUserName(username);
        state.setHost(ip);
        state.setKeyFile(keyfile);
        agent = MockSSHAgent.newAgentOnCleanMachine(state);
        state.setServiceInstanceIds(Lists.newArrayList(instanceId));
    }

    @AfterMethod(alwaysRun = true)
    public void after() {
        agent.close();
    }

    @Test(enabled = false)
    public void testPing() throws IOException {
        PingAgentTask task = new PingAgentTask();
        task.setProducerTimestamp(100L);
        agent.ping(task);
        Assert.assertEquals(task.getProducerTimestamp(), (Long) state.getLastPingSourceTimestamp());
        // TODO SSH test failed ping
    }

    @Test(enabled = false)
    public void testServiceInstanceLifecycle() throws IOException {
        // Upload dummy script (not necessary, simply reduces errors in ssh output)
        LifecycleState lifecycleState = new LifecycleState("dummy_start");
        uploadResourceBasedScript(agent.getSSHClient(), lifecycleState);

        // write
        ServiceInstanceTask task = new ServiceInstanceTask();
        task.setLifecycleState(lifecycleState);
        task.setStateId(instanceId);
        ServiceInstanceState serviceInstanceState = new ServiceInstanceState();
        serviceInstanceState.setServiceId(serviceId);
        serviceInstanceState.setAgentId(agentId);
        serviceInstanceState.setStateMachine(new LifecycleStateMachine());
        ServiceInstanceStateHolder holder = new ServiceInstanceStateHolder(serviceInstanceState);
        agent.serviceInstanceLifecycle(task, holder);
    }

    @Test(enabled = false, dependsOnMethods = "testServiceInstanceLifecycle")
    public void testRecoverServiceInstanceState() throws IOException {
        // setup
        testServiceInstanceLifecycle();

        // read
        RecoverServiceInstanceStateTask task = new RecoverServiceInstanceStateTask();
        task.setStateId(instanceId);
        task.setConsumerId(agentId);
        task.setServiceId(serviceId);
        task.setStateMachine(new LifecycleStateMachine());
        ServiceInstanceStateHolder holder = new ServiceInstanceStateHolder(null);
        agent.recoverServiceInstanceState(task, holder);
        ServiceInstanceState readServiceInstanceState = holder.get();
        Assert.assertNotNull(readServiceInstanceState);
    }

    @Test(enabled = false, dependsOnMethods = "testServiceInstanceLifecycle")
    public void testInjectPropertyToInstance() throws IOException {
        // setup
        testServiceInstanceLifecycle();

        // update
        ServiceInstanceStateHolder holder = callInjectPropertyToInstance();

        // read updated state
        RecoverServiceInstanceStateTask task2 = new RecoverServiceInstanceStateTask();
        task2.setStateId(instanceId);
        task2.setConsumerId(agentId);
        task2.setServiceId(serviceId);
        agent.recoverServiceInstanceState(task2, holder);
        ServiceInstanceState readServiceInstanceState = holder.get();

        // verify
        Assert.assertNotNull(readServiceInstanceState);
        Assert.assertEquals(readServiceInstanceState.getProperty("name"), "king");
    }

    @Test(enabled = false, dependsOnMethods = "testInjectPropertyToInstance")
    public void testRemoveServiceInstance() throws IOException {
        RemoveServiceInstanceFromAgentTask task = new RemoveServiceInstanceFromAgentTask();
        task.setInstanceId(instanceId);
        agent.removeServiceInstance(task);
        state.setServiceInstanceIds(Lists.newArrayList(instanceId));
        try {
            callInjectPropertyToInstance();
            Assert.fail("Expected service instance state to be removed");
        } catch (IllegalStateException probableExpected) {
            Assert.assertEquals(probableExpected.getMessage(), "missing service instance state");
        }
    }

    @Test(enabled = false)
    public void testServiceInstanceLifecycleWithProperties() throws IOException {
        MockSSHAgent.AgentSSHClient sshClient = agent.getSSHClient();

        // setup test properties
        String fileName = "filename";
        String fileContent = "filecontent";
        LifecycleStateMachine lifecycleStateMachine = new LifecycleStateMachine();
        LifecycleState lifecycleState = new LifecycleState("sshmockscript_start");
        LifecycleName lifecycleName = LifecycleName.fromLifecycleState(lifecycleState);
        lifecycleStateMachine.getProperties().put("name", fileName);
        lifecycleStateMachine.getProperties().put("content", fileContent);
        String parentPathToGeneratedFile =  Joiner.on('/').join(MockSSHAgent.SCRIPTS_ROOT, lifecycleName.getName());
        String pathToGeneratedFile = Joiner.on('/').join(parentPathToGeneratedFile, fileName);

        // copy resource script into scripts folder on remote machine
        uploadResourceBasedScript(sshClient, lifecycleState);

        // clean evn
        sshClient.removeFileIfExists(pathToGeneratedFile);

        // write
        ServiceInstanceTask task = new ServiceInstanceTask();
        task.setStateId(instanceId);
        task.setLifecycleState(lifecycleState);
        ServiceInstanceState serviceInstanceState = new ServiceInstanceState();
        serviceInstanceState.setServiceId(serviceId);
        serviceInstanceState.setAgentId(agentId);
        serviceInstanceState.setStateMachine(lifecycleStateMachine);
        ServiceInstanceStateHolder holder = new ServiceInstanceStateHolder(serviceInstanceState);
        agent.serviceInstanceLifecycle(task, holder);

        Optional<String> optionalContent = sshClient.getString(pathToGeneratedFile);
        Assert.assertTrue(optionalContent.isPresent(), "Missing file");
        Assert.assertEquals(optionalContent.get().trim(), fileContent, "Wrong file content");
    }

    private void uploadResourceBasedScript(MockSSHAgent.AgentSSHClient sshClient, LifecycleState lifecycleState) {
        String scriptName = lifecycleState.getName() + ".sh";
        LifecycleName lifecycleName = LifecycleName.fromLifecycleState(lifecycleState);
        String scriptParentPath = Joiner.on('/').join(MockSSHAgent.SCRIPTS_ROOT, lifecycleName.getName());
        String resourcePath = Joiner.on('/').join(MockSSHAgent.class.getPackage().getName().replace('.', '/'),
                scriptName);
        URL scriptResource = Resources.getResource(resourcePath);
        String content = null;
        try {
            content = Resources.toString(scriptResource, Charsets.UTF_8);
        } catch (IOException e) {
            Assert.fail("Failed reading script source", e);
        }
        sshClient.putString(scriptParentPath, scriptName, content);
    }

    private ServiceInstanceStateHolder callInjectPropertyToInstance() throws IOException {
        SetInstancePropertyTask task = new SetInstancePropertyTask();
        task.setStateId(instanceId);
        task.setPropertyName("name");
        task.setPropertyValue("king");
        ServiceInstanceStateHolder holder = new ServiceInstanceStateHolder(null);
        agent.injectPropertyToInstance(task, holder);
        return holder;
    }

    /**
     * Holder for {@link ServiceInstanceState} instances.
     */
    private static class ServiceInstanceStateHolder implements TaskConsumerStateModifier<ServiceInstanceState> {
        ServiceInstanceState serviceInstanceState;
        ServiceInstanceStateHolder(ServiceInstanceState state) {
            this.serviceInstanceState = state;
        }
        @Override
        public void put(ServiceInstanceState state) {
            serviceInstanceState = state;
        }
        @Override
        public ServiceInstanceState get() {
            return serviceInstanceState;
        }
    }

}
