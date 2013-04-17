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
package org.cloudifysource.cosmo.resource;

import com.beust.jcommander.internal.Maps;
import com.google.common.base.Throwables;
import com.google.common.util.concurrent.Uninterruptibles;
import com.ning.http.client.AsyncHttpClient;
import com.sun.jersey.api.client.Client;
import com.sun.jersey.api.client.WebResource;
import com.sun.jersey.api.client.config.DefaultClientConfig;
import org.cloudifysource.cosmo.kvstore.KVStoreServer;
import org.cloudifysource.cosmo.orchestrator.workflow.RuoteWorkflow;
import org.cloudifysource.cosmo.orchestrator.workflow.Workflow;
import org.cloudifysource.cosmo.resource.mock.ResourceMonitorMock;
import org.cloudifysource.cosmo.resource.mock.ResourceProvisioningServerListener;
import org.cloudifysource.cosmo.resource.mock.ResourceProvisioningServerMock;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * @author Itai Frenkel
 * @since 0.1
 */
public class StartVirtualMachineTest {

    private ResourceProvisioningServerMock resourceProvisioningServer;
    private URI resourceProvisioningUri;
    private KVStoreServer kvstoreServer;
    private URI kvstoreUri;
    private AsyncHttpClient asyncHttpClient;

    @BeforeMethod
    @Parameters({ "provisioningPort", "kvstorePort" })
    public void beforeMethod(@Optional("8080") int provisioningPort,
                             @Optional("8081") int kvstorePort) {
        resourceProvisioningServer = new ResourceProvisioningServerMock();
        resourceProvisioningServer.start(provisioningPort);
        resourceProvisioningUri = URI.create("http://localhost:" + provisioningPort + "/");

        kvstoreServer = new KVStoreServer();
        kvstoreServer.start(kvstorePort);
        kvstoreUri = URI.create("http://localhost:" + kvstorePort + "/");

        asyncHttpClient = new AsyncHttpClient();
    }

    @AfterMethod
    public void afterMethod() {
        resourceProvisioningServer.stop();
        kvstoreServer.stop();
    }

    @Test
    public void testStartVM() {
        try {
            final Client client = Client.create(new DefaultClientConfig());
            resourceProvisioningServer.setListener(new ResourceProvisioningServerListener() {
                @Override
                public void onRequest() {
                    try {
                        new Thread(new Runnable() {
                            @Override
                            public void run() {
                                Uninterruptibles.sleepUninterruptibly(1, TimeUnit.SECONDS);
                                final WebResource webResource = client.resource(kvstoreUri + "virtual_machine");
                                webResource.put("1");
                            }
                        }).start();
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            });

            final Map<String, Object> properties = Maps.newHashMap();
            properties.put("rest_put.cloud_provisioning.host", resourceProvisioningUri.toString());
            properties.put("rest_put.cloud_provisioning.path", "start_virtual_machine/1");
            properties.put("rest_get.kvstore.host", kvstoreUri.toString());
            properties.put("rest_get.kvstore.path", "virtual_machine");
            properties.put("rest_get.kvstore.response", "1");
            properties.put("rest_get.kvstore.timeout", "30");
            final Workflow workflow =
                    RuoteWorkflow.createFromFile("workflows/radial/vm_appliance.radial", properties);
            workflow.execute();

            assertThat(resourceProvisioningServer.getRequestsCount()).isEqualTo(1);

            final WebResource webResource = client.resource(kvstoreUri + "virtual_machine");
            final String s = webResource.get(String.class);
            assertThat(s).isEqualTo("1");

        } catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }

    @Test
    public void testMonitorVM() throws ExecutionException, InterruptedException {
        ResourceMonitorMock monitor = new ResourceMonitorMock(asyncHttpClient);
        URI resourceId = kvstoreUri.resolve("vm/1");
        monitor.setState(resourceId, "starting").get();
        monitor.setState(resourceId, "started").get();
    }


}

