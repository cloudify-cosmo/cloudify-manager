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

import com.google.common.base.Function;
import com.google.common.base.Preconditions;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.google.common.collect.Sets;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * Important assumptions:
 * 1. Single writer from a single thread will be the only one updating the cache state
 *
 * TODO: Write a short summary of this type's roles and responsibilities.
 *
 * @author Dan Kilman
 * @since 0.1
 */
public class StateCache {

    private final Object cacheMapLock = new Object();
    private final NamedLockProvider lockProvider = new NamedLockProvider();

    private final Map<String, Object> cache;
    private final ExecutorService executorService;
    private final Map<Condition, Set<CallbackContext>> listeners;

    private StateCache(Map<String, Object> initialState, ExecutorService executorService) {
        this.executorService = executorService;
        this.cache = Maps.newHashMap(initialState);
        this.listeners = Maps.newHashMap();
    }

    public void close() {
        executorService.shutdown();
    }

    public Object put(String key, Object value) {

        Object previous;

        ReentrantReadWriteLock lockForKey = lockProvider.forName(key);

        // before modifying this key, check if it is not locked by any wait for state calls
        lockForKey.writeLock().lock();
        try {
            // protected the underlying map (a call to snapshot might be going on).
            synchronized (cacheMapLock) {
                previous = cache.put(key, value);
            }
        } finally {
            lockForKey.writeLock().unlock();
        }

        StateCacheSnapshot snapshot = null;
        List<Condition> conditionsToRemove = null;

        // iterate through all listeners. (this might be optimizied in the future)
        for (Map.Entry<Condition, Set<CallbackContext>> entry : listeners.entrySet()) {
            Condition condition = entry.getKey();
            Set<CallbackContext> callbackContexts = entry.getValue();

            // if condition doesn't apply, move to next one
            if (!condition.applies(conditionStateCacheSnapshotInstance)) {
                continue;
            }

            // only create snapshot once as it will not change.
            if (snapshot == null) {
                snapshot = snapshot();
            }

            if (conditionsToRemove == null) {
                conditionsToRemove = Lists.newArrayList();
            }

            // submit callback tasks
            if (callbackContexts != null) {
                for (final CallbackContext callbackContext : callbackContexts) {
                    submitStateChangeNotificationTask(callbackContext, snapshot.asMap());
                }
            }
        }

        if (conditionsToRemove != null) {
            for (Condition condition : conditionsToRemove) {
                listeners.remove(condition);
            }
        }

        return previous;

    }

    public StateCacheSnapshot snapshot() {
        synchronized (cacheMapLock) {
            return new ExternalStateCacheSnapshot(ImmutableMap.copyOf(cache));
        }
    }

    public void waitForKeyValueState(final Object receiver,
                                     final Object context,
                                     final String key,
                                     final Object value,
                                     final StateChangeCallback callback) {
        Preconditions.checkNotNull(key);
        Preconditions.checkNotNull(value);
        Condition condition = new KeyValueCondition(key, value);
        waitForState(receiver, context, condition, callback);
    }

    private void waitForState(final Object receiver,
                              final Object context,
                              final Condition condition,
                              final StateChangeCallback callback) {
        CallbackContext callbackContext = new CallbackContext(receiver, context, callback);

        List<String> keyNamesToLock = condition.keysToLock();
        List<ReentrantReadWriteLock> keysInLockOrder = Lists.transform(keyNamesToLock, new Function<String,
                ReentrantReadWriteLock>() {
            public ReentrantReadWriteLock apply(String key) {
                return lockProvider.forName(key);
            }
        });
        List<ReentrantReadWriteLock> keysInUnlockOrder = Lists.reverse(keysInLockOrder);

        for (ReentrantReadWriteLock lock : keysInLockOrder) {
            lock.readLock().lock();
        }
        try {
            synchronized (cacheMapLock) {
                if (condition.applies(conditionStateCacheSnapshotInstance)) {
                    submitStateChangeNotificationTask(callbackContext, snapshot().asMap());
                    return;
                }
            }

            Set<CallbackContext> conditionCallbacks = listeners.get(condition);
            if (conditionCallbacks == null) {
                conditionCallbacks = Sets.newHashSet();
            }
            conditionCallbacks.add(callbackContext);
            listeners.put(condition, conditionCallbacks);
        } finally {
            for (ReentrantReadWriteLock lock : keysInUnlockOrder) {
                lock.readLock().unlock();
            }
        }
    }

    private void submitStateChangeNotificationTask(final CallbackContext callbackContext,
                                                   final ImmutableMap<String, Object> snapshot) {
        executorService.submit(new Runnable() {
            @Override
            public void run() {
                callbackContext.getCallback().onStateChange(callbackContext.getReceiver(),
                        callbackContext.getContext(),
                        StateCache.this,
                        snapshot);
            }
        });
    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    public static class Builder {
        private ExecutorService executorService;
        private Map<String, Object> initialState;

        public StateCache build() {
            return new StateCache(
                initialState != null ? initialState : Collections.<String, Object>emptyMap(),
                executorService != null ? executorService : Executors.newSingleThreadExecutor()
            );
        }

        public StateCache.Builder initialState(Map<String, Object> initialState) {
            this.initialState = initialState;
            return this;
        }

    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    public interface StateCacheSnapshot {
        Object get(String key);
        boolean containsKey(String key);
        ImmutableMap<String, Object> asMap();
    }

    private final ConditionStateCacheSnapshot conditionStateCacheSnapshotInstance =
            new ConditionStateCacheSnapshot();

    // all operations are synchronized by 'cacheMapLock'
    /**
     * @since 0.1
     * @author Dan Kilman
     */
    private class ConditionStateCacheSnapshot implements StateCacheSnapshot {

        @Override
        public Object get(String key) {
            synchronized (cacheMapLock) {
                return cache.get(key);
            }
        }

        @Override
        public boolean containsKey(String key) {
            synchronized (cacheMapLock) {
                return cache.containsKey(key);
            }
        }

        @Override
        public ImmutableMap<String, Object> asMap() {
            throw new UnsupportedOperationException("condition snapshot cannot be viewed as an immutable map");
        }
    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    public static class ExternalStateCacheSnapshot implements StateCacheSnapshot {

        private final ImmutableMap<String, Object> snapshot;

        public ExternalStateCacheSnapshot(ImmutableMap<String, Object> snapshot) {
            this.snapshot = snapshot;
        }

        @Override
        public Object get(String key) {
            return snapshot.get(key);
        }

        @Override
        public boolean containsKey(String key) {
            return snapshot.containsKey(key);
        }

        @Override
        public ImmutableMap<String, Object> asMap() {
            return snapshot;
        }
    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    private static class CallbackContext {

        private final Object receiver;
        private final Object context;
        private final StateChangeCallback callback;

        public CallbackContext(Object receiver, Object context, StateChangeCallback callback) {
            this.receiver = receiver;
            this.context = context;
            this.callback = callback;
        }

        public StateChangeCallback getCallback() {
            return callback;
        }

        public Object getContext() {
            return context;
        }

        public Object getReceiver() {
            return receiver;
        }
    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    private interface Condition {
        boolean applies(StateCacheSnapshot snapshot);
        List<String> keysToLock();
    }

    /**
     * @since 0.1
     * @author Dan Kilman
     */
    private static class KeyValueCondition implements Condition {

        private final String key;
        private final Object value;

        public KeyValueCondition(String key, Object value) {
            this.key = key;
            this.value = value;
        }

        @Override
        public boolean applies(StateCacheSnapshot snapshot) {
            return value != null ? value.equals(snapshot.get(key)) : snapshot.get(key) == null;
        }

        @Override
        public List<String> keysToLock() {
            return ImmutableList.of(key);
        }
    }

}
