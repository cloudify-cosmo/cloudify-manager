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
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.romix.scala.collection.concurrent.TrieMap;

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

    private final NamedLockProvider lockProvider = new NamedLockProvider();

    private final TrieMap<String, Object> cache;
    private final ExecutorService executorService;
    private final ConcurrentMap<String, CallbackContext> listeners;

    private StateCache(Map<String, Object> initialState) {
        this.executorService = Executors.newSingleThreadExecutor();
        this.cache = createCache(initialState);

        // Concurrent - listeners are queried and added on subscribeToStateChanges
        //              listeners are iterated and removed on put

        this.listeners = Maps.newConcurrentMap();
    }

    private static TrieMap<String, Object> createCache(Map<String, Object> initialState) {
        final TrieMap<String, Object> trieMap = TrieMap.empty();
        for (Map.Entry<String,Object> entry : initialState.entrySet())
            trieMap.put(entry.getKey(), entry.getValue());
        return trieMap;
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
            previous = cache.put(key, value);
        } finally {
            lockForKey.writeLock().unlock();
        }

        final Map<String, Object> snapshot = snapshot();

        Iterator<Map.Entry<String, CallbackContext>> iterator = listeners.entrySet().iterator();

        while (iterator.hasNext()) {
            Map.Entry<String, CallbackContext> entry = iterator.next();

            CallbackContext callbackContext = entry.getValue();
            Condition condition = callbackContext.getCondition();

            // if condition doesn't apply, move to next one
            if (!condition.applies(snapshot)) {
                continue;
            }

            submitStateChangeNotificationTask(callbackContext, snapshot);
        }

        return previous;

    }

    public Map<String, Object> snapshot() {
        return Collections.unmodifiableMap(cache.readOnlySnapshot());
    }

    public String subscribeToKeyValueStateChanges(Object receiver,
                                                  Object context,
                                                  final String key,
                                                  StateChangeCallback callback) {
        Preconditions.checkNotNull(key);
        Condition condition = new Condition() {
            @Override
            public boolean applies(Map<String,Object > snapshot) {
                return snapshot.containsKey(key);
            }

            @Override
            public List<String> keysToLock() {
                return ImmutableList.of(key);
            }
        };
        return subscribeToStateChanges(receiver, context, condition, callback);
    }


    private String subscribeToStateChanges(final Object receiver,
                                           final Object context,
                                           final Condition condition,
                                           final StateChangeCallback callback) {
        String callbackUID = UUID.randomUUID().toString();

        CallbackContext callbackContext = new CallbackContext(callbackUID, receiver, context, callback, condition);

        // obtain refernce to named locks relevent for this condition
        // and create locking/unlocking ordered lists.
        List<String> keyNamesToLock = Lists.newArrayList(condition.keysToLock());
        Collections.sort(keyNamesToLock);
        List<ReentrantReadWriteLock> keysInLockOrder = Lists.transform(keyNamesToLock, new Function<String,
                ReentrantReadWriteLock>() {
            public ReentrantReadWriteLock apply(String key) {
                return lockProvider.forName(key);
            }
        });

        // lock in locking order
        for (ReentrantReadWriteLock lock : keysInLockOrder) {
            lock.readLock().lock();
        }
        try {

            // add listener for condition
            listeners.put(callbackUID, callbackContext);

            // if condition already applies, submit notification task now and return.
            if (condition.applies(snapshot())) {
                submitStateChangeNotificationTask(callbackContext, snapshot());
            }

            return callbackUID;
        } finally {
            // unconditionStateCacheViewlock in reverse locking order
            for (ReentrantReadWriteLock lock : Lists.reverse(keysInLockOrder)) {
                lock.readLock().unlock();
            }
        }
    }

    public void removeCallback(final String callbackUID) {
        listeners.remove(callbackUID);
    }

    private void submitStateChangeNotificationTask(final CallbackContext callbackContext,
                                                   final Map<String, Object> snapshot) {
        executorService.submit(new Runnable() {
            @Override
            public void run() {
                //If the subscriber was removed on previous callback invocation but a following change occurred,
                // do not call the callback again
                if (!listeners.containsKey(callbackContext.getCallbackUID()))
                    return;

                boolean removeListener = callbackContext.getCallback().onStateChange(callbackContext.getReceiver(),
                                            callbackContext.getContext(),
                                            StateCache.this,
                                            snapshot);
                if (removeListener)
                    listeners.remove(callbackContext.getCallbackUID());
            }
        });
    }

    /**
     * @author Dan Kilman
     * @since 0.1
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
