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

import com.google.common.collect.ImmutableMap;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumer;
import org.cloudifysource.cosmo.messaging.consumer.MessageConsumerListener;
import org.cloudifysource.cosmo.statecache.messages.StateChangedMessage;

import java.net.URI;

/**
 * Holds a cache of the distributed system state. The state
 * is updated in real-time by listening to {@link org.cloudifysource.cosmo.statecache.messages.StateChangedMessage}s
 *
 * @author itaif
 * @since 0.1
 */
public class RealTimeStateCache implements StateCacheReader {

    protected final Logger logger = LoggerFactory.getLogger(this.getClass());

    private final MessageConsumer consumer;
    private final URI messageTopic;
    private final StateCache stateCache;
    private final MessageConsumerListener messageConsumerListener;

    public RealTimeStateCache(URI messageTopic,
                              MessageConsumer messageConsumer,
                              StateCache stateCache) {
        this.consumer = messageConsumer;
        this.messageTopic = messageTopic;
        this.stateCache = stateCache;

        this.messageConsumerListener = new MessageConsumerListener() {
            @Override
            public void onMessage(URI uri, Object message) {
                if (message instanceof StateChangedMessage) {
                    final StateChangedMessage update = (StateChangedMessage) message;
                    RealTimeStateCache.this.stateCache.put(update.getResourceId(), update.getState());
                } else {
                    throw new IllegalArgumentException("Cannot handle message " + message);
                }
            }

            @Override
            public void onFailure(Throwable t) {
                RealTimeStateCache.this.messageConsumerFailure(t);
            }
        };
    }

    public void start() {
        this.consumer.addListener(messageTopic, messageConsumerListener);
    }

    public void stop() {
        this.consumer.removeListener(messageConsumerListener);
    }

    private void messageConsumerFailure(Throwable t) {
        //TODO: Propagate Error
        System.err.println(t);
    }

    @Override
    public ImmutableMap<String, Object> snapshot() {
        return stateCache.snapshot();
    }

    @Override
    public String subscribeToKeyValueStateChanges(Object receiver,
                                                  Object context,
                                                  String key,
                                                  Object value,
                                                  StateChangeCallback callback) {
        return stateCache.subscribeToKeyValueStateChanges(receiver, context, key, value, callback);
    }

    @Override
    public String subscribeToKeyValueStateChanges(Object receiver,
                                                  Object context,
                                                  String key,
                                                  StateChangeCallback stateChangeCallback) {
        return stateCache.subscribeToKeyValueStateChanges(receiver, context, key, stateChangeCallback);
    }

    @Override
    public void removeCallback(String callbackUID) {
        stateCache.removeCallback(callbackUID);
    }

}
