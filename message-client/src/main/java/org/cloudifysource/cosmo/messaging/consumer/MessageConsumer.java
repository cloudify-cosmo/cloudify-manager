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

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Throwables;
import com.google.common.collect.Maps;
import com.ning.http.client.FluentCaseInsensitiveStringsMap;
import org.atmosphere.wasync.Client;
import org.atmosphere.wasync.ClientFactory;
import org.atmosphere.wasync.Decoder;
import org.atmosphere.wasync.Event;
import org.atmosphere.wasync.Function;
import org.atmosphere.wasync.Request;
import org.atmosphere.wasync.RequestBuilder;
import org.atmosphere.wasync.Socket;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.ObjectMapperFactory;

import java.io.IOException;
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
    private ObjectMapper mapper;
    protected Logger logger = LoggerFactory.getLogger(this.getClass());
    public MessageConsumer() {
        client = ClientFactory.getDefault().newClient();
        mapper = ObjectMapperFactory.newObjectMapper();
    }

    public <T> void addListener(final URI uri, final MessageConsumerListener<T> listener) {

        if (uri.getPath().contains("_")) {
            throw new IllegalArgumentException("Due to a known issue uri cannot contain underscores");
        }

        final RequestBuilder request =
                client.newRequestBuilder()
                        .method(Request.METHOD.GET)
                        .uri(uri.toString())
                        .decoder(new Decoder<String, T>() {
                            @Override
                            public T decode(Event type, String data) {

                                data = data.trim();
                                if (data.startsWith("<html>")) {
                                    throw new IllegalStateException(
                                            "Server returned unexpected response " + data);
                                }
                                // Padding
                                if (data.length() == 0) {
                                    return null;
                                }

                                if (type.equals(Event.MESSAGE)) {
                                    try {
                                        final T message = (T) mapper.readValue(data, Object.class);
                                        return message;
                                    } catch (IOException e) {
                                        if (data.equals("CLOSE")) {
                                            //Suppress bug.
                                            //https://github.com/Atmosphere/wasync/issues/34
                                            //Event type should be Event.CLOSE
                                            return null;
                                        }
                                        throw new IllegalStateException("Failed to decode " + data, e);
                                    }
                                } else if (type.equals(Event.OPEN) ||
                                        type.equals(Event.CLOSE)) {
                                    return null;
                                } else if (type.equals(Event.ERROR)) {
                                    throw new IllegalStateException("Communication error " + data);
                                } else {
                                    throw new IllegalStateException("Unexpected type=" + type + " data=" + data);
                                }
                            }
                        })
                        .transport(Request.TRANSPORT.LONG_POLLING);
        final Socket socket =  client.create();
        sockets.put(listener, socket);
        try {
            socket.on("STATUS", new Function<Integer>() {
                @Override
                public void on(Integer statusCode) {
                    if (statusCode >= 400) {
                        socket.close();
                    }
                }
            });
            socket.on(Event.MESSAGE.name(), new Function<Object>() {
                @Override
                public void on(Object message) {
                    if (message != null &&
                        isNotHeader(listener, message)) {
                        listener.onMessage(uri, (T) message);
                    }
                }

                /**
                 * workaround for bug https://github.com/Atmosphere/wasync/issues/35
                 */
                private boolean isNotHeader(MessageConsumerListener<T> listener, Object message) {
                    if (message instanceof FluentCaseInsensitiveStringsMap) {
                        return false;
                    }
                    return true;
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
            removeListener(listener);
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
