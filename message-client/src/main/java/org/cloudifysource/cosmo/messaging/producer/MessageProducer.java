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
package org.cloudifysource.cosmo.messaging.producer;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Throwables;
import com.google.common.util.concurrent.ListenableFuture;
import com.ning.http.client.AsyncHttpClient;
import com.ning.http.client.Response;
import org.cloudifysource.cosmo.messaging.ObjectMapperFactory;

import java.io.IOException;
import java.net.URI;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Client for sending messages to the message broker.
 *
 * @param <T> The message type
 * @author itaif
 * @since 0.1
 */
public class MessageProducer<T> {

    AsyncHttpClient client;
    ObjectMapper mapper;

    public MessageProducer() {
        client = new AsyncHttpClient();
        mapper = ObjectMapperFactory.newObjectMapper();
    }

    public ListenableFuture send(URI uri, Object message) {
        try {
            final String json = mapper.writerWithType(message.getClass()).writeValueAsString(message);
            return convertListenableFuture(
                    client.preparePost(uri.toString())
                            .setBody(json)
                            .execute());
        } catch (IOException e) {
            throw Throwables.propagate(e);
        }
    }

    private ListenableFuture convertListenableFuture(final com.ning.http.client.ListenableFuture<Response> future) {
        return new ListenableFuture() {
            @Override
            public void addListener(Runnable listener, Executor executor) {
                future.addListener(listener, executor);
            }

            @Override
            public boolean cancel(boolean mayInterruptIfRunning) {
                return future.cancel(mayInterruptIfRunning);
            }

            @Override
            public boolean isCancelled() {
                return future.isCancelled();
            }

            @Override
            public boolean isDone() {
                return future.isDone();
            }

            @Override
            public Object get() throws InterruptedException, ExecutionException {
                return future.get();
            }

            @Override
            public Object get(long timeout, TimeUnit unit)
                throws InterruptedException, ExecutionException, TimeoutException {
                return future.get(timeout, unit);
            }
        };
    }
}
