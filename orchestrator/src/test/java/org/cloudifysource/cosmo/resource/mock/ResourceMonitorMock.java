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
package org.cloudifysource.cosmo.resource.mock;

import com.google.common.base.Throwables;
import com.ning.http.client.AsyncCompletionHandler;
import com.ning.http.client.AsyncHttpClient;
import com.ning.http.client.ListenableFuture;
import com.ning.http.client.Response;

import javax.ws.rs.core.MediaType;
import java.io.IOException;
import java.net.URI;

import static org.fest.assertions.api.Assertions.assertThat;

/**
 * Monitors a resource and updates the k/v store with the new state.
 * @author Itai Frenkel
 * @since 0.1
 */
public class ResourceMonitorMock {

    private final AsyncHttpClient asyncHttpClient;

    public ResourceMonitorMock(AsyncHttpClient asyncHttpClient) {
        this.asyncHttpClient = asyncHttpClient;
    }

    public ListenableFuture<Void> setState(URI resourceId, String state) {
        try {
            return asyncHttpClient
                    .preparePut(resourceId.toString())
                    //.addHeader("If-None-Match", "*")
                    .addHeader("Content-Length", String.valueOf(state.length()))
                    .addHeader("Content-Type", MediaType.APPLICATION_JSON)
                    .setBody(state)
                    .execute(new AsyncCompletionHandler<Void>() {

                        @Override
                        public Void onCompleted(Response response) throws Exception {
                            assertThat(response.getStatusCode()).isEqualTo(200);
                            return null;
                        }

                        @Override
                        public void onThrowable(Throwable t) {
                            throw Throwables.propagate(t);
                        }
                    });
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }
}
