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
package org.cloudifysource.cosmo.messaging.consumer;

import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import org.atmosphere.wasync.Client;
import org.atmosphere.wasync.ClientFactory;
import org.atmosphere.wasync.Function;
import org.atmosphere.wasync.Request;
import org.atmosphere.wasync.RequestBuilder;
import org.atmosphere.wasync.Socket;

import java.net.URI;
import java.util.Map;

/**
 * Client for receiving messages from the message broker.
 * Call {@link #addListener(URI, MessageConsumerListener)} to start receiving messages.
 *
 * Call {@link #removeListener(MessageConsumerListener)} to stop receiving messages.
 * Not removing the listener results in resource leaks.
 *
 * @author itaif
 * @since 0.1
 */
public class MessageConsumer {

    private final Client client;
    private final Map<MessageConsumerListener, Socket> sockets = Maps.newConcurrentMap();

    public MessageConsumer() {
        client = ClientFactory.getDefault().newClient();
    }

    public void addListener(final URI uri, final MessageConsumerListener listener) {
        final RequestBuilder request =
                client.newRequestBuilder()
                        .method(Request.METHOD.GET)
                        .uri(uri.toString())
                        .transport(Request.TRANSPORT.STREAMING);
        Socket socket =  client.create();
        sockets.put(listener, socket);
        try {
            socket.on(new Function<String>() {
                @Override
                public void on(String message) {
                    listener.onMessage(uri, message);
                }
            });
            socket.on(new Function<Throwable>() {

                @Override
                public void on(Throwable t) {
                    listener.onFailure(t);
                }
            });
            socket.open(request.build());
        } catch (Throwable t) {
            sockets.remove(listener);
            throw Throwables.propagate(t);
        }
    }

    public boolean removeListener(MessageConsumerListener listener) {
        final Socket socket = sockets.remove(listener);
        if (socket != null) {
            socket.close();
            return true;
        }
        return false;
    }

    public void removeAllListeners() {
        for (MessageConsumerListener listener : sockets.keySet()) {
            removeListener(listener);
        }
    }
}
