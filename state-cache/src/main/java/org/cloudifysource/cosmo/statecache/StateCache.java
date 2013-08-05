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

import com.google.common.base.Optional;
import com.google.common.base.Preconditions;
import com.google.common.collect.HashMultimap;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Multimaps;
import com.google.common.collect.SetMultimap;
import com.romix.scala.collection.concurrent.TrieMap;
import org.cloudifysource.cosmo.logging.Logger;
import org.cloudifysource.cosmo.logging.LoggerFactory;

import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.Lock;

/**
 * The state cache holds the state of each resource, the state of each resource is a collection of properties
 * and their values.
 *
 * @author Eitan Yanovsky
 * @since 0.1
 */
public class StateCache implements AutoCloseable {

    private final TrieMap<StateCacheProperty, StateCacheValue> cache;
    private final SetMultimap<String, StateCacheListenerHolder> listeners;
    private final NamedLockProvider lockProvider;
    private final ExecutorService executorService;

    private final Logger logger = LoggerFactory.getLogger(this.getClass());

    /**
     * Holds a listener and it's id, used for scanning the listeners multimap and remove the listener
     * according to its id.
     */
    private static class StateCacheListenerHolder {

        private final StateCacheListener listener;
        private final String listenerId;

        public static StateCacheListenerHolder template(String listenerId) {
            return new StateCacheListenerHolder(null, listenerId);
        }

        public static StateCacheListenerHolder create(StateCacheListener listener, String listenerId) {
            return new StateCacheListenerHolder(listener, listenerId);
        }

        private StateCacheListenerHolder(StateCacheListener listener, String listenerId) {
            this.listener = listener;
            this.listenerId = listenerId;
        }

        public StateCacheListener getListener() {
            return listener;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;

            StateCacheListenerHolder that = (StateCacheListenerHolder) o;

            if (listenerId != null ? !listenerId.equals(that.listenerId) : that.listenerId != null) return false;

            return true;
        }

        @Override
        public int hashCode() {
            return listenerId != null ? listenerId.hashCode() : 0;
        }

        public String getListenerId() {
            return listenerId;
        }
    }

    public StateCache() {
        this.cache = TrieMap.empty();
        this.lockProvider = new NamedLockProvider();
        this.executorService = Executors.newSingleThreadExecutor();
        this.listeners = Multimaps.synchronizedSetMultimap(HashMultimap.<String, StateCacheListenerHolder>create());
    }

    @Override
    public void close() throws Exception {
        executorService.shutdownNow();
    }

    public void put(String resourceId, String property, StateCacheValue value) {
        Preconditions.checkNotNull(resourceId);
        Preconditions.checkNotNull(property);
        Preconditions.checkNotNull(value);
        Preconditions.checkNotNull(value.getState());
        final Lock lock = lockProvider.forName(resourceId);
        lock.lock();
        try {
            cache.put(new StateCacheProperty(resourceId, property), value);
            final TrieMap<StateCacheProperty, StateCacheValue> snapshot = cache.snapshot();
            final Set<StateCacheListenerHolder> resourceListeners = listeners.get(resourceId);
            /** Ignoring instruction appearing on
             * {@link Multimaps#synchronizedMultimap(com.google.common.collect.Multimap)} because when this multi-value
             * is accessed it is always under a specific lock for this resource id, meaning there aren't two concurrent
             * threads accessing it hence we get a legit snapshot of the values */
            for (StateCacheListenerHolder listenerHolder : resourceListeners) {
                submitTriggerEventTask(resourceId, listenerHolder.getListener(), listenerHolder.getListenerId(),
                        snapshot);
            }
        } finally {
            lock.unlock();
        }
    }

    public String subscribe(String resourceId, StateCacheListener listener) {
        Preconditions.checkNotNull(resourceId);
        Preconditions.checkNotNull(listener);
        final Lock lock = lockProvider.forName(resourceId);
        lock.lock();
        try {
            final String listenerId = UUID.randomUUID().toString();
            listeners.put(resourceId, StateCacheListenerHolder.create(listener, listenerId));
            final TrieMap<StateCacheProperty, StateCacheValue> snapshot = cache.snapshot();
            for (Map.Entry<StateCacheProperty, StateCacheValue> entry : snapshot.entrySet()) {
                if (entry.getKey().getResourceId().equals(resourceId)) {
                    submitTriggerEventTask(resourceId, listener, listenerId, snapshot);
                    break;
                }
            }
            return listenerId;
        } finally {
            lock.unlock();
        }
    }

    private void submitTriggerEventTask(
            final String resourceId,
            final StateCacheListener listener,
            final String listenerId,
            final TrieMap<StateCacheProperty, StateCacheValue> snapshot) {
        executorService.submit(new Runnable() {
            @Override
            public void run() {
                if (!listeners.containsEntry(resourceId, StateCacheListenerHolder.template(listenerId))) {
                    return;
                }
                boolean remove = true;
                try {
                    remove = listener.onResourceStateChange(new StateCacheSnapshot() {
                        @Override
                        public boolean containsProperty(String resourceId, String property) {
                            return snapshot.containsKey(new StateCacheProperty(resourceId, property));
                        }

                        @Override
                        public Optional<StateCacheValue> getProperty(String resourceId, String property) {
                            final StateCacheProperty stateCacheProperty = new StateCacheProperty(resourceId, property);
                            return Optional.fromNullable(snapshot.get(stateCacheProperty));
                        }

                        @Override
                        public ImmutableMap<String, StateCacheValue> getResourceProperties(String resourceId) {
                            final ImmutableMap.Builder<String, StateCacheValue> builder = ImmutableMap.builder();
                            for (Map.Entry<StateCacheProperty, StateCacheValue> entry : snapshot.entrySet()) {
                                if (entry.getKey().getResourceId().equals(resourceId))
                                    builder.put(entry.getKey().getProperty(), entry.getValue());
                            }
                            return builder.build();
                        }
                    });
                } catch (Exception e) {
                    logger.debug("Exception while invoking state change listener, listener will be removed", e);
                } finally {
                    if (remove) {
                        removeSubscription(resourceId, listenerId);
                    }
                }
            }
        });
    }

    public void removeSubscription(String resourceId, String listenerId) {
        Preconditions.checkNotNull(resourceId);
        Preconditions.checkNotNull(listenerId);
        final Lock lock = lockProvider.forName(resourceId);
        lock.lock();
        try {
            listeners.remove(resourceId, StateCacheListenerHolder.template(listenerId));
        } finally {
            lock.unlock();
        }
    }
}
