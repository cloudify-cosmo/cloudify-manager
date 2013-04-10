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
import org.cloudifysource.cosmo.resource.mock.ResourceProvisionerServerMock;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Optional;
import org.testng.annotations.Parameters;
import org.testng.annotations.Test;
import com.ning.http.client.*;
import static org.fest.assertions.api.Assertions.*;

import java.util.concurrent.Future;

public class StartVirtualMachineTest {

    ResourceProvisionerServerMock server;
    private String restUri;
    private AsyncHttpClient asyncHttpClient;

    @BeforeMethod
    @Parameters({ "port" })
    public void beforeMethod(@Optional("8080") int port) {
        server = new ResourceProvisionerServerMock();
        server.start(port);

        restUri = "http://localhost:" + port + "/";
        asyncHttpClient = new AsyncHttpClient();
    }

    @AfterMethod
    public void afterMethod() {
        server.stop();
    }

    @Test
    public void testStartVM() {
        try {
            Future<Integer> f =
                    asyncHttpClient
                    .preparePut(restUri + "start_virtual_machine/1")
                    .execute(
                            new AsyncCompletionHandler<Integer>(){

                                @Override
                                public Integer onCompleted(Response response) throws Exception{
                                    return response.getStatusCode();
                                }

                                @Override
                                public void onThrowable(Throwable t){
                                    throw Throwables.propagate(t);
                                }
                            });

            assertThat(f.get()).isEqualTo(204);
        }
        catch (Exception e) {
            throw Throwables.propagate(e);
        }
    }
}
