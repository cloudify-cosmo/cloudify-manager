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

import com.google.common.base.Throwables;
import com.ning.http.client.AsyncCompletionHandler;
import com.ning.http.client.AsyncHttpClient;
import com.ning.http.client.Response;
import org.cloudifysource.cosmo.kvstore.KVStoreServer;
import org.cloudifysource.cosmo.resource.mock.ResourceMonitorMock;
import org.cloudifysource.cosmo.resource.mock.ResourceProvisioningServerMock;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;

import java.net.URI;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;

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
            Future<Integer> f =
                    asyncHttpClient
                    .preparePut(resourceProvisioningUri + "start_virtual_machine/1")
                    .execute(
                            new AsyncCompletionHandler<Integer>() {

                                @Override
                                public Integer onCompleted(Response response) throws Exception {
                                    return response.getStatusCode();
                                }

                                @Override
                                public void onThrowable(Throwable t) {
                                    throw Throwables.propagate(t);
                                }
                            });

            assertThat(f.get()).isEqualTo(204);
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

