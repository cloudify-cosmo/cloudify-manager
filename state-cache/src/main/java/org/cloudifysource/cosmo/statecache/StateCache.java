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
import com.google.common.collect.ImmutableMap;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;

import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentMap;
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
    private final ConditionStateCacheSnapshot conditionStateCacheSnapshot;
    private final ExecutorService executorService;
    private final ConcurrentMap<String, CallbackContext> listeners;

    private StateCache(Map<String, Object> initialState) {
        this.executorService = Executors.newSingleThreadExecutor();
        this.cache = Maps.newHashMap(initialState);
        this.conditionStateCacheSnapshot = new ConditionStateCacheSnapshot(cache, cacheMapLock);

        // Concurrent - listeners are queried and added on subscribeToStateChanges
        //              listeners are iterated and removed on put
        this.listeners = Maps.newConcurrentMap();
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

        Iterator<Map.Entry<String, CallbackContext>> iterator = listeners.entrySet().iterator();

        while (iterator.hasNext()) {
            Map.Entry<String, CallbackContext> entry = iterator.next();

            CallbackContext callbackContext = entry.getValue();
            Condition condition = callbackContext.getCondition();

            // if condition doesn't apply, move to next one
            if (!condition.applies(conditionStateCacheSnapshot)) {
                continue;
            }

            // only create snapshot once as it will not change.
            if (snapshot == null) {
                snapshot = snapshot();
            }

            iterator.remove();

            submitStateChangeNotificationTask(callbackContext, snapshot.asMap());
        }

        return previous;

    }

    public StateCacheSnapshot snapshot() {
        synchronized (cacheMapLock) {
            return new ExternalStateCacheSnapshot(ImmutableMap.copyOf(cache));
        }
    }

    public String subscribeToKeyValueStateChanges(final Object receiver,
                                                  final Object context,
                                                  final String key,
                                                  final Object value,
                                                  final StateChangeCallback callback) {
        Preconditions.checkNotNull(key);
        Preconditions.checkNotNull(value);
        Condition condition = new KeyValueCondition(key, value);
        return subscribeToStateChanges(receiver, context, condition, callback);
    }

    private String subscribeToStateChanges(final Object receiver,
                                           final Object context,
                                           final Condition condition,
                                           final StateChangeCallback callback) {
        String callbackUID = UUID.randomUUID().toString();

        CallbackContext callbackContext = new CallbackContext(receiver, context, callback, condition);

        // obtain refernce to named locks relevent for this condition
        // and create locking/unlocking ordered lists.
        List<String> keyNamesToLock = condition.keysToLock();
        List<ReentrantReadWriteLock> keysInLockOrder = Lists.transform(keyNamesToLock, new Function<String,
                ReentrantReadWriteLock>() {
            public ReentrantReadWriteLock apply(String key) {
                return lockProvider.forName(key);
            }
        });
        List<ReentrantReadWriteLock> keysInUnlockOrder = Lists.reverse(keysInLockOrder);

        // lock in locking order
        for (ReentrantReadWriteLock lock : keysInLockOrder) {
            lock.readLock().lock();
        }
        try {

            synchronized (cacheMapLock) {
                // if condition already applies, submit notification task now and return.
                if (condition.applies(conditionStateCacheSnapshot)) {
                    submitStateChangeNotificationTask(callbackContext, snapshot().asMap());
                    return callbackUID;
                }
            }

            // add listener for condition
            listeners.put(callbackUID, callbackContext);
            return callbackUID;
        } finally {
            // unlock in reverse locking order
            for (ReentrantReadWriteLock lock : keysInUnlockOrder) {
                lock.readLock().unlock();
            }
        }
    }

    public void removeCallback(final String callbackUID) {
        listeners.remove(callbackUID);
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
        private Map<String, Object> initialState;

        public StateCache build() {
            return new StateCache(
                initialState != null ? initialState : Collections.<String, Object>emptyMap()
            );
        }

        public StateCache.Builder initialState(Map<String, Object> initialState) {
            this.initialState = initialState;
            return this;
        }

    }

}
